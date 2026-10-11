"""Authentification, autorisation et limitation de débit.

- Mots de passe : PBKDF2-HMAC-SHA256 (600 000 itérations, sel aléatoire de 16 octets),
  comparaison en temps constant. Aucun mot de passe en clair n'est stocké.
- Jetons : JWT signés HS256 avec `APP_SECRET_KEY` (durée de vie limitée). Le jeton porte
  l'identité, les rôles et les groupes de diffusion de l'utilisateur.
- Rôles : `viewer` (consultation), `manager` (+ recherche d'experts), `admin` (+ gestion des
  documents et de l'ingestion).
- Limitation de débit : fenêtre glissante en mémoire par utilisateur (protection contre les
  abus et contre l'épuisement du quota LLM). Pour plusieurs instances, un stockage partagé
  (Redis) serait nécessaire : limite documentée.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import yaml

ITERATIONS = 600_000
ROLE_ORDER = {"viewer": 0, "manager": 1, "admin": 2}


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iterations))
    return hmac.compare_digest(digest, base64.b64decode(digest_b64))


@dataclass(frozen=True)
class User:
    username: str
    display_name: str
    roles: frozenset[str]
    groups: frozenset[str]
    password_hash: str = ""

    def has_role(self, role: str) -> bool:
        return any(ROLE_ORDER.get(r, -1) >= ROLE_ORDER[role] for r in self.roles)

    def public(self) -> dict:
        return {"username": self.username, "display_name": self.display_name, "roles": sorted(self.roles),
                "groups": sorted(self.groups)}


class UserStore:
    def __init__(self, path: str | Path) -> None:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        self.users = {
            u["username"]: User(u["username"], u.get("display_name", u["username"]), frozenset(u.get("roles", ["viewer"])),
                                frozenset(u.get("groups", ["ALL"])), u["password_hash"])
            for u in data.get("users", [])
        }
        # Empreinte factice : le temps de réponse est le même que l'utilisateur existe ou non.
        self._dummy = hash_password(secrets.token_hex(8))

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.users.get(username)
        valid = verify_password(password, user.password_hash if user else self._dummy)
        return user if (user and valid) else None


class TokenService:
    def __init__(self, secret: str, ttl_minutes: int) -> None:
        if len(secret) < 32:
            raise ValueError("APP_SECRET_KEY doit contenir au moins 32 caractères.")
        self.secret = secret
        self.ttl = ttl_minutes

    def issue(self, user: User) -> str:
        now = datetime.now(UTC)
        payload = {"sub": user.username, "name": user.display_name, "roles": sorted(user.roles),
                   "groups": sorted(user.groups), "iat": now, "exp": now + timedelta(minutes=self.ttl)}
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def decode(self, token: str) -> User | None:
        try:
            payload = jwt.decode(token, self.secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        except jwt.PyJWTError:
            return None
        return User(payload["sub"], payload.get("name", payload["sub"]), frozenset(payload.get("roles", [])),
                    frozenset(payload.get("groups", [])))


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            calls = self._calls[key]
            while calls and now - calls[0] > self.window:
                calls.popleft()
            if len(calls) >= self.max_calls:
                return False
            calls.append(now)
            return True
