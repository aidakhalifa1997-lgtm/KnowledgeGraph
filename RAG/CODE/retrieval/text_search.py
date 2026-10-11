"""Recherche lexicale (BM25 via l'index plein texte Lucene de Neo4j) et recherche vectorielle
(index HNSW de Neo4j), toutes deux filtrées par les documents autorisés."""

from __future__ import annotations

import re

from core.text import STOPWORDS, fold_accents
from knowledge_graph.client import Neo4jClient
from knowledge_graph.schema import CHUNK_FULLTEXT, VECTOR_INDEX
from retrieval.embeddings import Embedder

_LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)')


def _escape(text: str) -> str:
    return _LUCENE_SPECIAL.sub(lambda m: "\\" + m.group(1), text)


def build_lucene_query(question: str, phrases: list[str] | None = None) -> str:
    """Requête Lucene : termes porteurs de sens reliés par OR, plus les noms d'entités
    reconnues en expressions exactes (boostées). Les caractères spéciaux sont échappés et les
    termes mis en minuscules (« AND », « OR » ne deviennent pas des opérateurs) : la question
    de l'utilisateur ne peut pas modifier la syntaxe de la requête."""
    terms = []
    for word in re.findall(r"[\wÀ-ÿ'-]+", question):
        bare = word.strip("'-").lower()
        if len(bare) < 2 or fold_accents(bare) in STOPWORDS:
            continue
        terms.append(_escape(bare))
    clauses = ['"' + _escape(p.lower()) + '"^2' for p in (phrases or []) if p.strip()]
    clauses += terms
    return " OR ".join(dict.fromkeys(clauses)) or "*"


class TextSearch:
    def __init__(self, client: Neo4jClient, embedder: Embedder) -> None:
        self.client = client
        self.embedder = embedder

    def lexical(self, question: str, allowed: list[str], k: int, phrases: list[str] | None = None) -> list[tuple[str, float]]:
        query = build_lucene_query(question, phrases)
        if query == "*":
            return []
        rows = self.client.read(
            f"""CALL db.index.fulltext.queryNodes('{CHUNK_FULLTEXT}', $q, {{limit: $limit}})
                YIELD node, score
                WHERE node.doc_id IN $allowed
                RETURN node.id AS id, score ORDER BY score DESC LIMIT $k""",
            q=query, limit=max(k * 5, 50), allowed=allowed, k=k)
        return [(r["id"], float(r["score"])) for r in rows]

    def vector(self, question: str, allowed: list[str], k: int) -> list[tuple[str, float]]:
        embedding = [float(x) for x in self.embedder.embed([question])[0]]
        # Le filtre d'accès s'applique après la recherche approximative : on demande plus de
        # candidats que nécessaire et on élargit si le filtrage en élimine trop.
        pool = max(k * 4, 40)
        while True:
            rows = self.client.read(
                f"""CALL db.index.vector.queryNodes('{VECTOR_INDEX}', $pool, $embedding)
                    YIELD node, score
                    WHERE node.doc_id IN $allowed
                    RETURN node.id AS id, score ORDER BY score DESC LIMIT $k""",
                pool=pool, embedding=embedding, allowed=allowed, k=k)
            if len(rows) >= k or pool >= 1000:
                return [(r["id"], float(r["score"])) for r in rows]
            pool *= 3
