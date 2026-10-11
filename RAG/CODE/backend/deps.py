"""Dépendances FastAPI : accès aux services, utilisateur courant, contrôle des rôles."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.security import User
from retrieval.access import AccessContext
from services import Services

_bearer = HTTPBearer(auto_error=False)


def get_services(request: Request) -> Services:
    return request.app.state.services


def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise",
                            headers={"WWW-Authenticate": "Bearer"})
    user = request.app.state.tokens.decode(credentials.credentials)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide ou expiré",
                            headers={"WWW-Authenticate": "Bearer"})
    request.state.username = user.username
    return user


def access_context(user: User = Depends(current_user)) -> AccessContext:
    return AccessContext(user.username, user.groups, user.roles)


def require_role(role: str):
    def checker(user: User = Depends(current_user)) -> User:
        if not user.has_role(role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Rôle « {role} » requis")
        return user

    return checker


def allowed_documents(services: Services = Depends(get_services),
                      access: AccessContext = Depends(access_context)) -> list[str]:
    return services.access.allowed_doc_ids(access)
