"""Routes de l'API REST (préfixe /api)."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status

from backend.deps import access_context, allowed_documents, current_user, get_services, require_role
from backend.schemas import AskRequest, LoginRequest, QueryRecommendationRequest
from backend.security import User
from knowledge_graph.queries import GraphQueries
from retrieval.access import AccessContext
from services import Services

router = APIRouter(prefix="/api")


def _queries(services: Services) -> GraphQueries:
    return GraphQueries(services.client)


# ---------------------------------------------------------------- authentification
@router.post("/auth/login", tags=["auth"])
def login(payload: LoginRequest, request: Request) -> dict:
    limiter = request.app.state.login_limiter
    client_ip = request.client.host if request.client else "inconnu"
    if not limiter.allow(f"{client_ip}:{payload.username}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives de connexion, réessayez plus tard")
    user = request.app.state.users.authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants invalides")
    return {"access_token": request.app.state.tokens.issue(user), "token_type": "bearer", "user": user.public()}


@router.get("/auth/me", tags=["auth"])
def me(user: User = Depends(current_user)) -> dict:
    return user.public()


# ---------------------------------------------------------------- questions-réponses
@router.post("/ask", tags=["questions"])
def ask(payload: AskRequest, request: Request, services: Services = Depends(get_services),
        access: AccessContext = Depends(access_context)) -> dict:
    if not request.app.state.ask_limiter.allow(access.username):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Limite de questions par minute atteinte")
    return services.workflow.run(payload.question, access, strategy=payload.strategy)


@router.get("/workflow/diagram", tags=["questions"])
def workflow_diagram(services: Services = Depends(get_services), _: User = Depends(current_user)) -> dict:
    return {"mermaid": services.workflow.mermaid()}


# ---------------------------------------------------------------- graphe
@router.get("/graph/schema", tags=["graphe"])
def graph_schema(services: Services = Depends(get_services), _: User = Depends(current_user)) -> dict:
    return _queries(services).schema()


@router.get("/graph/stats", tags=["graphe"])
def graph_stats(services: Services = Depends(get_services), allowed: list[str] = Depends(allowed_documents)) -> dict:
    return _queries(services).stats(allowed)


@router.get("/graph/search", tags=["graphe"])
def graph_search(q: str = Query(min_length=1, max_length=100), types: list[str] | None = Query(default=None),
                 services: Services = Depends(get_services), allowed: list[str] = Depends(allowed_documents)) -> list[dict]:
    return _queries(services).search_entities(q, allowed, types)


@router.get("/graph/overview", tags=["graphe"])
def graph_overview(limit: int = Query(default=60, ge=5, le=200), types: list[str] | None = Query(default=None),
                   services: Services = Depends(get_services), allowed: list[str] = Depends(allowed_documents)) -> dict:
    return _queries(services).overview(allowed, limit=limit, types=types)


@router.get("/graph/node/{node_id}", tags=["graphe"])
def graph_node(node_id: str, services: Services = Depends(get_services),
               allowed: list[str] = Depends(allowed_documents)) -> dict:
    queries = _queries(services)
    result = queries.document(node_id, allowed) if node_id.startswith("doc-") else queries.entity(node_id, allowed)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élément introuvable ou non autorisé")
    return result


@router.get("/graph/neighborhood/{node_id}", tags=["graphe"])
def graph_neighborhood(node_id: str, depth: int = Query(default=1, ge=1, le=2),
                       relation_types: list[str] | None = Query(default=None),
                       node_types: list[str] | None = Query(default=None), limit: int = Query(default=80, ge=1, le=300),
                       services: Services = Depends(get_services), allowed: list[str] = Depends(allowed_documents)) -> dict:
    return _queries(services).neighborhood(node_id, allowed, depth, relation_types, node_types, limit)


# ---------------------------------------------------------------- experts
@router.get("/experts/domains", tags=["experts"])
def expert_domains(services: Services = Depends(get_services), allowed: list[str] = Depends(allowed_documents),
                   _: User = Depends(require_role("manager"))) -> list[dict]:
    return services.experts.domains(allowed)


@router.get("/experts", tags=["experts"])
def experts(domain: str = Query(min_length=2, max_length=120), limit: int = Query(default=10, ge=1, le=30),
            services: Services = Depends(get_services), allowed: list[str] = Depends(allowed_documents),
            _: User = Depends(require_role("manager"))) -> dict:
    domain_id = services.experts.resolve_domain(domain)
    if domain_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domaine non reconnu")
    from expert_discovery.service import LIMITS

    results = services.experts.find_experts(domain_id, allowed, limit=limit)
    return {"domain": {"id": domain_id, "name": services.referential.name(domain_id)}, "limits": LIMITS,
            "experts": [{"person_id": r.person_id, "name": r.name, "score": r.score, "confidence": r.confidence,
                         "justification": r.justification, "mention_count": r.mention_count,
                         "evidence": [e.__dict__ for e in r.evidence]} for r in results]}


# ---------------------------------------------------------------- recommandations
def _serialize_recommendations(items) -> list[dict]:
    return [r.__dict__ for r in items]


@router.get("/recommendations/document/{doc_id}", tags=["recommandations"])
def recommend_for_document(doc_id: str, limit: int = Query(default=5, ge=1, le=20),
                           mode: str = Query(default="hybrid", pattern="^(hybrid|content|graph)$"),
                           services: Services = Depends(get_services),
                           allowed: list[str] = Depends(allowed_documents)) -> list[dict]:
    if doc_id not in allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document introuvable ou non autorisé")
    return _serialize_recommendations(services.recommendations.for_document(doc_id, allowed, limit, mode))


@router.post("/recommendations/query", tags=["recommandations"])
def recommend_for_query(payload: QueryRecommendationRequest, services: Services = Depends(get_services),
                        allowed: list[str] = Depends(allowed_documents)) -> list[dict]:
    return _serialize_recommendations(services.recommendations.for_query(payload.text, allowed, payload.limit))


# ---------------------------------------------------------------- documents
@router.get("/documents", tags=["documents"])
def list_documents(services: Services = Depends(get_services), allowed: list[str] = Depends(allowed_documents),
                   user: User = Depends(current_user)) -> list[dict]:
    # Les administrateurs voient aussi les documents écartés (doublons, quarantaine, rejets).
    return _queries(services).documents(allowed, include_hidden=user.has_role("admin"))


@router.get("/documents/{doc_id}", tags=["documents"])
def get_document(doc_id: str, services: Services = Depends(get_services),
                 allowed: list[str] = Depends(allowed_documents), user: User = Depends(current_user)) -> dict:
    result = _queries(services).document(doc_id, allowed, include_hidden=user.has_role("admin"))
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document introuvable ou non autorisé")
    return result


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


@router.post("/documents", tags=["documents"], status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...), services: Services = Depends(get_services),
                          _: User = Depends(require_role("admin"))) -> dict:
    name = _SAFE_NAME.sub("_", Path(file.filename or "document").name)[:120].strip("._") or "document"
    if Path(name).suffix.lower() not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Formats acceptés : PDF, DOCX, TXT")
    max_bytes = services.settings.max_upload_mb * 1024 * 1024
    uploads = Path(services.settings.uploads_dir)
    uploads.mkdir(parents=True, exist_ok=True)
    target = uploads / name
    size = 0
    with target.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                    f"Fichier supérieur à {services.settings.max_upload_mb} Mo")
            out.write(chunk)
    result = services.pipeline.ingest_file(target)
    services.pipeline.finalize()
    services.refresh_after_ingestion()
    if result.outcome in ("rejected", "error"):
        target.unlink(missing_ok=True)
    return result.model_dump()


@router.delete("/documents/{doc_id}", tags=["documents"])
def delete_document(doc_id: str, services: Services = Depends(get_services),
                    _: User = Depends(require_role("admin"))) -> dict:
    state = services.client.read("MATCH (d:Document {id: $id}) RETURN d.source_path AS path", id=doc_id)
    if not state:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document introuvable")
    services.pipeline.delete(doc_id)
    path = Path(state[0]["path"] or "")
    if path.is_file() and Path(services.settings.uploads_dir).resolve() in path.resolve().parents:
        path.unlink()  # seuls les fichiers téléversés sont supprimés du disque
    services.refresh_after_ingestion()
    return {"deleted": doc_id}


# ---------------------------------------------------------------- administration
@router.post("/ingestion/run", tags=["administration"])
def run_ingestion(services: Services = Depends(get_services), _: User = Depends(require_role("admin"))) -> dict:
    report = services.pipeline.sync_directory(services.settings.documents_dir)
    services.refresh_after_ingestion()
    return {"run_id": report.run_id, "duration_seconds": report.duration_seconds, "files_seen": report.files_seen,
            "outcomes": {k: report.count(k) for k in ("ingested", "updated", "unchanged", "duplicate", "quarantined",
                                                      "rejected", "error")},
            "deleted": report.deleted_documents,
            "details": [r.model_dump(include={"file_name", "outcome", "message"}) for r in report.results]}


@router.get("/ingestion/runs", tags=["administration"])
def ingestion_runs(services: Services = Depends(get_services), _: User = Depends(require_role("admin"))) -> list[dict]:
    return [r["run"] for r in _queries(services).ingestion_runs()]


@router.get("/metrics", tags=["administration"])
def metrics(request: Request, _: User = Depends(require_role("admin"))) -> dict:
    return request.app.state.metrics.snapshot()
