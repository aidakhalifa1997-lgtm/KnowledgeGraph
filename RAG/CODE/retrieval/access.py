"""Contrôle d'accès aux documents (filtrage *avant* récupération).

Règle : un utilisateur voit un document si sa diffusion est « ALL » (tous collaborateurs) ou
si l'un de ses groupes figure dans la liste de diffusion du document. Seuls les documents
`active` ou `superseded` sont exploitables (doublons, quarantaine et rejets sont exclus).

Cette liste d'identifiants autorisés est passée en paramètre à TOUTES les requêtes de
recherche (lexicale, vectorielle, graphe) : un passage non autorisé n'entre jamais dans le
contexte du LLM, et une relation n'est visible que si au moins un de ses documents sources
est autorisé.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from knowledge_graph.client import Neo4jClient

SEARCHABLE = ["active", "superseded"]


@dataclass(frozen=True)
class AccessContext:
    username: str
    groups: frozenset[str]
    roles: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def system(cls) -> AccessContext:
        """Contexte technique (évaluations, scripts) : accès à tous les groupes."""
        return cls("system", frozenset({"*"}), frozenset({"admin"}))

    def can(self, role: str) -> bool:
        return role in self.roles or "admin" in self.roles


class AccessResolver:
    def __init__(self, client: Neo4jClient, ttl_seconds: float = 30.0) -> None:
        self.client = client
        self.ttl = ttl_seconds
        self._cache: dict[frozenset[str], tuple[float, list[str]]] = {}

    def allowed_doc_ids(self, access: AccessContext) -> list[str]:
        cached = self._cache.get(access.groups)
        if cached and time.monotonic() - cached[0] < self.ttl:
            return cached[1]
        rows = self.client.read(
            """MATCH (d:Document) WHERE d.status IN $statuses
               AND ('ALL' IN d.diffusion OR '*' IN $groups OR any(g IN d.diffusion WHERE g IN $groups))
               RETURN d.id AS id""", statuses=SEARCHABLE, groups=sorted(access.groups))
        ids = [r["id"] for r in rows]
        self._cache[access.groups] = (time.monotonic(), ids)
        return ids

    def invalidate(self) -> None:
        self._cache.clear()
