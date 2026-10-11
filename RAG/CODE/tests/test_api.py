"""Tests de l'API HTTP (FastAPI TestClient) branchée sur la base Neo4j de test."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.security import RateLimiter
from ingestion.processor import document_id_for

pytestmark = pytest.mark.integration
PASSWORD = "Demo-Orizia-2026"


@pytest.fixture(scope="module")
def client(integration_services):
    # Sans bloc `with` : le cycle de vie (fermeture des services) reste géré par la fixture de session.
    return TestClient(create_app(integration_services))


@pytest.fixture(scope="module")
def tokens(client):
    out = {}
    for username in ("admin", "manager.conformite", "collaborateur", "ingenieur.dsi"):
        response = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
        assert response.status_code == 200, response.text
        out[username] = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return out


def test_health_and_security_headers(client):
    response = client.get("/api/health")
    assert response.status_code == 200 and response.json()["neo4j"] == "up"
    for header in ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "X-Request-ID"):
        assert header in response.headers


def test_authentication_required_and_invalid_credentials(client):
    assert client.get("/api/graph/stats").status_code == 401
    assert client.get("/api/graph/stats", headers={"Authorization": "Bearer faux.jeton.signe"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "mauvais"}).status_code == 401


def test_me_returns_groups(client, tokens):
    me = client.get("/api/auth/me", headers=tokens["ingenieur.dsi"]).json()
    assert me["username"] == "ingenieur.dsi" and "DSI" in me["groups"]


def test_ask_respects_access_rights(client, tokens):
    body = {"question": "Quel est le RTO de CoreNova ?"}
    dsi = client.post("/api/ask", json=body, headers=tokens["ingenieur.dsi"]).json()
    collab = client.post("/api/ask", json=body, headers=tokens["collaborateur"]).json()
    assert dsi["status"] == "answered" and "4 heures" in dsi["answer"]
    assert collab["status"] == "abstained" and "4 heures" not in collab["answer"]


def test_ask_validates_input(client, tokens):
    assert client.post("/api/ask", json={"question": ""}, headers=tokens["collaborateur"]).status_code == 422
    assert client.post("/api/ask", json={"question": "x" * 5000}, headers=tokens["collaborateur"]).status_code == 422
    assert client.post("/api/ask", json={"question": "Test ?", "strategy": "inconnue"},
                       headers=tokens["collaborateur"]).status_code == 422


def test_ask_rate_limit(client, tokens):
    app = client.app
    original = app.state.ask_limiter
    app.state.ask_limiter = RateLimiter(1)
    try:
        body = {"question": "Quel est le délai d'accusé de réception d'une réclamation ?"}
        assert client.post("/api/ask", json=body, headers=tokens["collaborateur"]).status_code == 200
        assert client.post("/api/ask", json=body, headers=tokens["collaborateur"]).status_code == 429
    finally:
        app.state.ask_limiter = original


def test_roles(client, tokens):
    assert client.get("/api/experts?domain=KYC", headers=tokens["collaborateur"]).status_code == 403
    experts = client.get("/api/experts?domain=lutte anti-blanchiment", headers=tokens["manager.conformite"])
    assert experts.status_code == 200 and experts.json()["experts"]
    assert client.get("/api/metrics", headers=tokens["manager.conformite"]).status_code == 403
    assert client.get("/api/metrics", headers=tokens["admin"]).status_code == 200
    assert client.post("/api/ingestion/run", headers=tokens["collaborateur"]).status_code == 403


def test_documents_visibility(client, tokens):
    restricted = document_id_for("Post-mortem_incident_CoreNova_2025-10.txt")
    assert client.get(f"/api/documents/{restricted}", headers=tokens["collaborateur"]).status_code == 404
    assert client.get(f"/api/documents/{restricted}", headers=tokens["ingenieur.dsi"]).status_code == 200
    collab_docs = {d["id"] for d in client.get("/api/documents", headers=tokens["collaborateur"]).json()}
    assert restricted not in collab_docs


def test_graph_endpoints(client, tokens):
    headers = tokens["collaborateur"]
    assert client.get("/api/graph/schema", headers=headers).status_code == 200
    stats = client.get("/api/graph/stats", headers=headers).json()
    assert stats
    found = client.get("/api/graph/search?q=CoreNova", headers=headers).json()
    assert any(e["id"] == "sys:corenova" for e in found)
    hood = client.get("/api/graph/neighborhood/sys:corenova", headers=headers).json()
    assert hood["nodes"] and hood["edges"]
    assert client.get("/api/graph/node/inexistant", headers=headers).status_code == 404
    assert "graph TD" in client.get("/api/workflow/diagram", headers=headers).json()["mermaid"] or \
        "flowchart" in client.get("/api/workflow/diagram", headers=headers).json()["mermaid"]


def test_recommendations_endpoints(client, tokens):
    headers = tokens["collaborateur"]
    source = document_id_for("PRC-KYC-001_v2.0_entree_en_relation_connaissance_client.docx")
    items = client.get(f"/api/recommendations/document/{source}?mode=hybrid", headers=headers).json()
    assert items and all(i["reasons"] for i in items)
    query = client.post("/api/recommendations/query", json={"text": "continuité d'activité et sauvegardes"},
                        headers=headers)
    assert query.status_code == 200


def test_upload_and_delete_document(client, tokens):
    admin = tokens["admin"]
    content = "\n".join([
        "ORIZIA BANQUE — document fictif", "Référence : NS-TST-001", "Version : 1.0", "Date : 05/03/2026",
        "Direction propriétaire : Direction Conformité", "Rédacteur : Salma Idrissi", "Classification : Interne",
        "Diffusion : Tous collaborateurs", "=" * 40, "", "# Note de test du téléversement", "",
        "Cette note de service fictive sert uniquement à vérifier le téléversement par l'API. Elle rappelle que "
        "Sentinel KYC est utilisé pour la revue périodique des dossiers clients et que la Direction Conformité "
        "en contrôle l'application chaque trimestre."]).encode("utf-8")
    files = {"file": ("../../note test.txt", content, "text/plain")}
    assert client.post("/api/documents", files=files, headers=tokens["collaborateur"]).status_code == 403
    response = client.post("/api/documents", files=files, headers=admin)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["outcome"] == "ingested" and body["file_name"] == "note_test.txt", "nom de fichier assaini"
    doc_id = body["doc_id"]
    assert client.get(f"/api/documents/{doc_id}", headers=tokens["collaborateur"]).status_code == 200
    assert client.delete(f"/api/documents/{doc_id}", headers=tokens["collaborateur"]).status_code == 403
    assert client.delete(f"/api/documents/{doc_id}", headers=admin).status_code == 200
    assert client.get(f"/api/documents/{doc_id}", headers=admin).status_code == 404


def test_upload_rejects_unsupported_files(client, tokens):
    admin = tokens["admin"]
    exe = client.post("/api/documents", files={"file": ("outil.exe", b"MZ", "application/octet-stream")}, headers=admin)
    assert exe.status_code == 415
    fake = client.post("/api/documents", files={"file": ("faux.pdf", b"pas un pdf du tout", "application/pdf")},
                       headers=admin)
    assert fake.status_code == 201 and fake.json()["outcome"] == "rejected"
    client.delete(f"/api/documents/{fake.json()['doc_id']}", headers=admin)
