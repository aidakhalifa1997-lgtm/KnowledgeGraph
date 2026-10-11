"""Application FastAPI : configuration, intercepteurs (middlewares), gestion des erreurs.

Démarrage : uvicorn backend.main:create_app --factory --host 0.0.0.0 --port 8000
Documentation interactive : /api/docs
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import router
from backend.security import RateLimiter, TokenService, UserStore
from core.logging_config import configure_logging
from core.settings import get_settings
from knowledge_graph.client import GraphUnavailable
from services import Services, build_services

logger = logging.getLogger("api")
VERSION = "1.0.0"


class Metrics:
    """Compteurs simples en mémoire : nombre d'appels, erreurs et latences par route."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls: dict[str, int] = defaultdict(int)
        self.errors: dict[str, int] = defaultdict(int)
        self.latencies: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=500))

    def record(self, route: str, status_code: int, ms: float) -> None:
        with self._lock:
            self.calls[route] += 1
            if status_code >= 500:
                self.errors[route] += 1
            self.latencies[route].append(ms)

    def snapshot(self) -> dict:
        with self._lock:
            out = {}
            for route, values in self.latencies.items():
                ordered = sorted(values)
                out[route] = {"calls": self.calls[route], "errors_5xx": self.errors[route],
                              "p50_ms": round(statistics.median(ordered), 1),
                              "p95_ms": round(ordered[int(0.95 * (len(ordered) - 1))], 1)}
            return out


def create_app(services: Services | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        svc: Services = app.state.services
        if svc.client.ping():
            svc.ensure_schema()
            logger.info("Neo4j disponible, schéma vérifié")
        else:
            logger.error("Neo4j indisponible au démarrage : l'API répondra 503 jusqu'à son rétablissement")
        yield
        svc.close()

    app = FastAPI(title="Orizia Knowledge Graph Platform", version=VERSION, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.state.services = services or build_services(settings)
    app.state.users = UserStore(settings.users_file)
    secret = settings.app_secret_key.get_secret_value()
    if not secret:
        raise RuntimeError("APP_SECRET_KEY n'est pas défini : la signature des jetons est impossible.")
    app.state.tokens = TokenService(secret, settings.token_ttl_minutes)
    app.state.ask_limiter = RateLimiter(settings.ask_rate_limit_per_minute)
    app.state.login_limiter = RateLimiter(10, window_seconds=300)
    app.state.metrics = Metrics()

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def observability(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Erreur non gérée", extra={"request_id": request_id, "path": request.url.path})
            response = JSONResponse({"detail": "Erreur interne", "request_id": request_id}, status_code=500)
        ms = round((time.perf_counter() - started) * 1000, 1)
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        app.state.metrics.record(f"{request.method} {route_path}", response.status_code, ms)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        logger.info("requête", extra={"request_id": request_id, "method": request.method, "path": route_path,
                                       "status": response.status_code, "ms": ms,
                                       "user": getattr(request.state, "username", None)})
        return response

    @app.exception_handler(GraphUnavailable)
    async def graph_unavailable(_: Request, exc: GraphUnavailable):
        return JSONResponse({"detail": "Base de connaissances indisponible, réessayez dans un instant."}, status_code=503)

    @app.get("/api/health", tags=["supervision"])
    def health() -> dict:
        svc: Services = app.state.services
        neo4j_up = svc.client.ping()
        return {"status": "ok" if neo4j_up else "degraded", "version": VERSION, "neo4j": "up" if neo4j_up else "down",
                "llm_provider": settings.llm_provider if settings.llm_enabled else "offline",
                "embedding_provider": settings.embedding_provider}

    app.include_router(router)
    return app

