"""Recommandations explicables combinant contenu et graphe.

Pour un document source s et un candidat c :

    score(s, c) = α · sim_contenu(s, c) + β · recouvrement_entités(s, c) + γ · proximité_graphe(s, c)

- sim_contenu : cosinus entre les centroïdes des passages, normalisé min-max sur les candidats
  (les encodeurs statiques produisent des similarités très resserrées) ;
- recouvrement_entités : indice de Jaccard entre les ensembles de concepts, systèmes, procédures
  et projets mentionnés ;
- proximité_graphe : lien explicite dans le graphe — versions d'une même procédure (1,0), même
  entité décrite (1,0), relation directe entre les entités décrites (0,8), entité décrite par
  l'un et mentionnée par l'autre (0,6).

Chaque recommandation renvoie ses raisons (concepts communs, relation parcourue, version), ce qui
répond à l'exigence d'explicabilité (Guo et al., 2022). Les trois variantes `content`, `graph` et
`hybrid` sont comparées expérimentalement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.ontology import verbalize
from extraction.linker import EntityLinker
from knowledge_graph.client import Neo4jClient
from retrieval.embeddings import Embedder

MODES = {
    "hybrid": (0.4, 0.3, 0.3),
    "content": (1.0, 0.0, 0.0),
    "graph": (0.0, 0.5, 0.5),
}
OVERLAP_TYPES = ["Concept", "System", "Procedure", "Project"]


@dataclass
class Recommendation:
    doc_id: str
    title: str
    doc_type: str
    status: str
    reference: str | None
    score: float
    components: dict[str, float]
    reasons: list[str] = field(default_factory=list)


class RecommendationService:
    def __init__(self, client: Neo4jClient, linker: EntityLinker, embedder: Embedder) -> None:
        self.client = client
        self.linker = linker
        self.embedder = embedder

    def _load(self, allowed: list[str]) -> dict:
        docs = {r["id"]: r for r in self.client.read(
            """MATCH (d:Document) WHERE d.id IN $allowed
               RETURN d.id AS id, d.title AS title, d.doc_type AS doc_type, d.status AS status, d.reference AS reference""",
            allowed=allowed)}
        centroids = {}
        for row in self.client.read(
                "MATCH (d:Document)<-[:PART_OF]-(c:Chunk) WHERE d.id IN $allowed RETURN d.id AS id, collect(c.embedding) AS e",
                allowed=allowed):
            vec = np.mean(np.asarray(row["e"], dtype=np.float32), axis=0)
            centroids[row["id"]] = vec / (np.linalg.norm(vec) + 1e-9)
        entities = {r["id"]: dict(zip(r["ids"], r["names"], strict=False)) for r in self.client.read(
            """MATCH (d:Document)<-[:PART_OF]-(:Chunk)-[:MENTIONS]->(e:Entity)
               WHERE d.id IN $allowed AND e.type IN $types AND e.status = 'validated'
               WITH d, collect(DISTINCT e) AS es
               RETURN d.id AS id, [x IN es | x.id] AS ids, [x IN es | x.name] AS names""",
            allowed=allowed, types=OVERLAP_TYPES)}
        describes = {r["id"]: r["ids"] for r in self.client.read(
            "MATCH (d:Document)-[:DESCRIBES]->(e) WHERE d.id IN $allowed RETURN d.id AS id, collect(e.id) AS ids",
            allowed=allowed)}
        versions = {(r["a"], r["b"]) for r in self.client.read(
            "MATCH (a:Document)-[:SUPERSEDES]->(b:Document) WHERE a.id IN $allowed AND b.id IN $allowed "
            "RETURN a.id AS a, b.id AS b", allowed=allowed)}
        described_ids = sorted({e for ids in describes.values() for e in ids})
        links = {}
        if described_ids:
            for r in self.client.read(
                    """MATCH (a:Entity)-[r]-(b:Entity) WHERE a.id IN $ids AND b.id IN $ids AND a.id < b.id
                       AND type(r) IN ['DEPENDS_ON','IMPACTS','DELIVERS','REFERENCES','USES']
                       AND any(x IN r.source_doc_ids WHERE x IN $allowed)
                       RETURN a.id AS a, a.name AS an, b.id AS b, b.name AS bn, type(r) AS rel,
                              startNode(r).id = a.id AS forward""", ids=described_ids, allowed=allowed):
                text = verbalize(r["an"], r["rel"], r["bn"]) if r["forward"] else verbalize(r["bn"], r["rel"], r["an"])
                links[(r["a"], r["b"])] = links[(r["b"], r["a"])] = text
        return {"docs": docs, "centroids": centroids, "entities": entities, "describes": describes,
                "versions": versions, "links": links}

    def _proximity(self, data: dict, s: str, c: str) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0
        if (s, c) in data["versions"]:
            score, reasons = 1.0, ["version antérieure du même document"]
        elif (c, s) in data["versions"]:
            score, reasons = 1.0, ["version plus récente du même document"]
        ds, dc = set(data["describes"].get(s, [])), set(data["describes"].get(c, []))
        names_c, names_s = data["entities"].get(c, {}), data["entities"].get(s, {})
        if ds & dc:
            score = max(score, 1.0)
            shared = next(iter(ds & dc))
            reasons.append(f"décrit le même élément : {self.linker.ref.name(shared)}")
        for a in ds:
            for b in dc:
                if (a, b) in data["links"]:
                    score = max(score, 0.8)
                    reasons.append(f"relation dans le graphe : {data['links'][(a, b)]}")
        for a in ds:
            if a in names_c:
                score = max(score, 0.6)
                reasons.append(f"cite {self.linker.ref.name(a)}, objet du document source")
        for b in dc:
            if b in names_s:
                score = max(score, 0.6)
                reasons.append(f"porte sur {self.linker.ref.name(b)}, cité par le document source")
        return score, list(dict.fromkeys(reasons))

    def for_document(self, doc_id: str, allowed: list[str], limit: int = 5, mode: str = "hybrid") -> list[Recommendation]:
        if doc_id not in allowed:
            return []
        data = self._load(allowed)
        alpha, beta, gamma = MODES[mode]
        candidates = [d for d in data["docs"] if d != doc_id and d in data["centroids"]]
        if doc_id not in data["centroids"] or not candidates:
            return []
        sims = {c: float(data["centroids"][doc_id] @ data["centroids"][c]) for c in candidates}
        lo, hi = min(sims.values()), max(sims.values())
        source_entities = data["entities"].get(doc_id, {})
        results = []
        for c in candidates:
            content = (sims[c] - lo) / (hi - lo) if hi > lo else 0.0
            target_entities = data["entities"].get(c, {})
            shared = set(source_entities) & set(target_entities)
            union = set(source_entities) | set(target_entities)
            jaccard = len(shared) / len(union) if union else 0.0
            proximity, reasons = self._proximity(data, doc_id, c)
            score = alpha * content + beta * jaccard + gamma * proximity
            if shared:
                names = sorted(target_entities[e] for e in shared)[:5]
                reasons.append("éléments communs : " + ", ".join(names))
            if content >= 0.7:
                reasons.append(f"contenu sémantiquement proche (cosinus {sims[c]:.2f})")
            d = data["docs"][c]
            results.append(Recommendation(
                doc_id=c, title=d["title"], doc_type=d["doc_type"], status=d["status"], reference=d["reference"],
                score=round(score, 4), components={"content": round(content, 3), "entities": round(jaccard, 3),
                                                   "graph": round(proximity, 3)}, reasons=reasons[:5]))
        results.sort(key=lambda r: (-r.score, r.doc_id))
        return results[:limit]

    def for_query(self, text: str, allowed: list[str], limit: int = 5) -> list[Recommendation]:
        data = self._load(allowed)
        if not data["centroids"]:
            return []
        query_vec = self.embedder.embed([text])[0]
        linked = {m.entity_id for m in self.linker.find_mentions(text) if m.entity_id}
        sims = {d: float(query_vec @ v) for d, v in data["centroids"].items()}
        lo, hi = min(sims.values()), max(sims.values())
        results = []
        for doc_id, sim in sims.items():
            content = (sim - lo) / (hi - lo) if hi > lo else 0.0
            ents = data["entities"].get(doc_id, {})
            shared = linked & set(ents)
            overlap = len(shared) / len(linked) if linked else 0.0
            described = linked & set(data["describes"].get(doc_id, []))
            proximity = 1.0 if described else 0.0
            score = 0.4 * content + 0.3 * overlap + 0.3 * proximity
            reasons = []
            if described:
                reasons.append("décrit " + ", ".join(self.linker.ref.name(e) for e in described))
            if shared:
                reasons.append("cite " + ", ".join(sorted(ents[e] for e in shared)))
            if content >= 0.7:
                reasons.append(f"contenu proche de la requête (cosinus {sim:.2f})")
            d = data["docs"][doc_id]
            results.append(Recommendation(doc_id=doc_id, title=d["title"], doc_type=d["doc_type"], status=d["status"],
                                          reference=d["reference"], score=round(score, 4),
                                          components={"content": round(content, 3), "entities": round(overlap, 3),
                                                      "graph": proximity}, reasons=reasons))
        results.sort(key=lambda r: (-r.score, r.doc_id))
        return results[:limit]
