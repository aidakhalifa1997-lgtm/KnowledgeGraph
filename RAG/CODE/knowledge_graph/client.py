"""Connexion à Neo4j (pilote officiel `neo4j`).

Un seul pilote par processus (il gère un pool de connexions). Les requêtes sont toujours
paramétrées (`$param`) : aucune valeur fournie par un utilisateur n'est concaténée dans le
texte Cypher, ce qui protège contre l'injection Cypher. Les seuls éléments insérés
dynamiquement (étiquettes et types de relations) proviennent de listes blanches internes.
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from core.settings import Settings

logger = logging.getLogger(__name__)


class GraphUnavailable(RuntimeError):
    pass


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        self.database = database
        # Les notifications d'information du serveur (propriété encore inexistante sur une base
        # vide, etc.) sont désactivées : elles polluent les journaux sans signaler d'erreur.
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password), max_connection_pool_size=20,
                                                    connection_timeout=10, notifications_min_severity="OFF")

    @classmethod
    def from_settings(cls, settings: Settings) -> Neo4jClient:
        return cls(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password.get_secret_value(),
                   settings.neo4j_database)

    def close(self) -> None:
        self._driver.close()

    def ping(self) -> bool:
        try:
            self._driver.verify_connectivity()
            return True
        except (ServiceUnavailable, Neo4jError, OSError):
            return False

    def read(self, query: str, **params: Any) -> list[dict]:
        try:
            records, _, _ = self._driver.execute_query(query, params, database_=self.database, routing_="r")
        except ServiceUnavailable as exc:
            raise GraphUnavailable("Neo4j est indisponible") from exc
        return [r.data() for r in records]

    def write(self, query: str, **params: Any) -> list[dict]:
        try:
            records, _, _ = self._driver.execute_query(query, params, database_=self.database)
        except ServiceUnavailable as exc:
            raise GraphUnavailable("Neo4j est indisponible") from exc
        return [r.data() for r in records]

    def session(self):
        return self._driver.session(database=self.database)
