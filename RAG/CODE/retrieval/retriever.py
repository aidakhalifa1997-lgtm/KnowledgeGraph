"""Point d'entrée unique de la récupération, pour les quatre architectures comparées.

| Stratégie      | Sources combinées                                   |
|----------------|-----------------------------------------------------|
| `vector`       | recherche vectorielle seule (RAG classique)         |
| `lexical`      | BM25 seul (référence complémentaire)                |
| `hybrid`       | BM25 + vectoriel, fusion RRF (RAG hybride)          |
| `graph`        | passages issus du Knowledge Graph seul (GraphRAG)   |
| `hybrid_graph` | BM25 + vectoriel + graphe, fusion RRF pondérée      |

Toutes les stratégies reçoivent la même liste de documents autorisés et renvoient des passages
« hydratés » (texte + métadonnées du document) prêts à être cités.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from knowledge_graph.client import Neo4jClient
from retrieval.fusion import fuse_top_k
from retrieval.graph import GraphRetrieval, GraphRetriever
from retrieval.text_search import TextSearch

STRATEGIES = ("vector", "lexical", "hybrid", "graph", "hybrid_graph")


@dataclass
class RetrievedChunk:
    id: str
    doc_id: str
    text: str
    section: str
    page: int | None
    score: float
    ranks: dict[str, int]
    title: str
    reference: str | None
    version: str | None
    doc_date: str | None
    doc_type: str
    status: str
    file_name: str
    classification: str


@dataclass
class RetrievalResult:
    strategy: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    graph: GraphRetrieval | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)

    @property
    def doc_ranking(self) -> list[str]:
        ranking: list[str] = []
        for chunk in self.chunks:
            if chunk.doc_id not in ranking:
                ranking.append(chunk.doc_id)
        return ranking


class Retriever:
    def __init__(self, client: Neo4jClient, text_search: TextSearch, graph: GraphRetriever, *, rrf_k: int = 60,
                 candidate_pool: int = 40, source_guarantee: int = 1) -> None:
        self.client = client
        self.text = text_search
        self.graph = graph
        self.rrf_k = rrf_k
        self.pool = candidate_pool
        self.source_guarantee = source_guarantee

    def hydrate(self, ids: list[str]) -> dict[str, dict]:
        if not ids:
            return {}
        rows = self.client.read(
            """MATCH (c:Chunk)-[:PART_OF]->(d:Document) WHERE c.id IN $ids
               RETURN c.id AS id, c.doc_id AS doc_id, c.text AS text, c.section AS section, c.page AS page,
                      d.title AS title, d.reference AS reference, d.version AS version,
                      toString(d.doc_date) AS doc_date, d.doc_type AS doc_type, d.status AS status,
                      d.file_name AS file_name, d.classification AS classification""", ids=ids)
        return {r["id"]: r for r in rows}

    def retrieve(self, question: str, allowed: list[str], strategy: str = "hybrid_graph", k: int = 8, *,
                 graph_weight: float = 1.0, max_hops: int | None = None, extra_seeds: list[str] | None = None,
                 extra_terms: list[str] | None = None) -> RetrievalResult:
        if strategy not in STRATEGIES:
            raise ValueError(f"stratégie inconnue : {strategy}")
        result = RetrievalResult(strategy=strategy)
        rankings: dict[str, list[str]] = {}
        graph_result: GraphRetrieval | None = None
        query_text = question if not extra_terms else f"{question} {' '.join(extra_terms)}"

        if strategy in ("graph", "hybrid_graph"):
            t = time.perf_counter()
            graph_result = self.graph.retrieve(question, allowed, max_hops=max_hops, extra_seeds=extra_seeds)
            result.timings_ms["graph"] = round((time.perf_counter() - t) * 1000, 1)
            result.graph = graph_result
            rankings["graph"] = [cid for cid, _ in graph_result.chunk_scores]
        phrases = [s["surface"] for s in (graph_result.seeds if graph_result else []) if s.get("surface")]
        if strategy in ("lexical", "hybrid", "hybrid_graph"):
            t = time.perf_counter()
            rankings["lexical"] = [cid for cid, _ in self.text.lexical(query_text, allowed, self.pool, phrases)]
            result.timings_ms["lexical"] = round((time.perf_counter() - t) * 1000, 1)
        if strategy in ("vector", "hybrid", "hybrid_graph"):
            t = time.perf_counter()
            rankings["vector"] = [cid for cid, _ in self.text.vector(query_text, allowed, self.pool)]
            result.timings_ms["vector"] = round((time.perf_counter() - t) * 1000, 1)

        fused = fuse_top_k(rankings, k, k=self.rrf_k, weights={"graph": graph_weight}, guarantee=self.source_guarantee)
        details = self.hydrate([cid for cid, _, _ in fused])
        for cid, score, ranks in fused:
            d = details.get(cid)
            if d is None or d["doc_id"] not in set(allowed):
                continue  # garde-fou : jamais de passage hors périmètre autorisé
            result.chunks.append(RetrievedChunk(
                id=cid, doc_id=d["doc_id"], text=d["text"], section=d["section"] or "", page=d["page"],
                score=score, ranks=ranks, title=d["title"], reference=d["reference"], version=d["version"],
                doc_date=d["doc_date"], doc_type=d["doc_type"], status=d["status"], file_name=d["file_name"],
                classification=d["classification"]))
        return result
