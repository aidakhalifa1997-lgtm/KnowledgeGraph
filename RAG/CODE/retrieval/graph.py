"""Récupération guidée par le Knowledge Graph (GraphRAG « local »).

Étapes (inspirées de HippoRAG, Gutiérrez et al., 2024) :

1. **Ancrage** : les entités citées dans la question sont reconnues et reliées au graphe
   (« graines »). Un alias ambigu (« Sentinel ») produit plusieurs graines, et l'ambiguïté est
   signalée.
2. **Intention relationnelle** : des indices lexicaux de la question (« dépend », « équipe »,
   « expert »...) désignent les types de relations les plus utiles.
3. **Sous-graphe local** : chemins d'au plus `max_hops` relations sémantiques autour des
   graines, en ne conservant que les relations justifiées par au moins un document autorisé.
4. **Personalized PageRank** : une marche aléatoire qui revient aux graines avec probabilité
   α classe les entités du sous-graphe ; les relations correspondant à l'intention pèsent plus.
5. **Faits et passages** : les relations les mieux classées deviennent des faits citables
   (avec leurs documents sources) ; les passages qui prouvent ces faits et ceux qui mentionnent
   les entités les mieux classées sont classés pour le contexte.
6. **Chemins** : les chemins effectivement parcourus entre graines et entités importantes sont
   conservés tels quels pour l'explication (jamais reconstruits a posteriori).
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field

import numpy as np

from core.ontology import verbalize
from core.text import normalize_key
from extraction.linker import EntityLinker
from knowledge_graph.client import Neo4jClient
from knowledge_graph.schema import SEMANTIC_RELATIONS

INTENT_CUES: list[tuple[str, list[str]]] = [
    (r"depend|affect|impact|indisponib|panne|tomb|interrupt", ["DEPENDS_ON"]),
    (r"responsable|proprietaire|en charge|gere ", ["RESPONSIBLE_FOR", "OWNS", "PARTICIPATES_IN"]),
    (r"equipe|membre|particip|pilot|chef de projet|cheffe de projet|sponsor|interven|contribu|projets?\b",
     ["PARTICIPATES_IN"]),
    (r"travaill|direction|entite|pole|service|cellule|rattach|compos|organis", ["WORKS_IN", "PART_OF"]),
    (r"expert|expertise|competen|speciali|maitris|aider|tourner|connait", ["HAS_EXPERTISE"]),
    (r"livr|deploi|deploy|mis en place|mise en place", ["DELIVERS"]),
    (r"outil|applicati|utilis|systeme|logiciel", ["USES", "DEPENDS_ON", "RESPONSIBLE_FOR"]),
    (r"procedure|referenc|renvoi", ["REFERENCES", "USES", "OWNS", "IMPACTS"]),
    (r"evolu|impacte|modifi|revis|mise a jour|mis a jour", ["IMPACTS"]),
    (r"traite|concerne|porte sur|notion|concept", ["COVERS"]),
]
TRAVERSAL = [r for r in SEMANTIC_RELATIONS if r != "BELONGS_TO"]
ALPHA = 0.15  # probabilité de retour aux graines (PageRank personnalisé)


@dataclass
class Fact:
    id: str
    subject_id: str
    subject_name: str
    subject_type: str
    relation: str
    object_id: str
    object_name: str
    object_type: str
    roles: list[str]
    confidence: float
    source_doc_ids: list[str]
    evidence_chunk_ids: list[str]
    evidence_quotes: list[str]
    score: float = 0.0

    @property
    def text(self) -> str:
        return verbalize(self.subject_name, self.relation, self.object_name, self.roles)


@dataclass
class GraphRetrieval:
    seeds: list[dict] = field(default_factory=list)
    ambiguous: list[dict] = field(default_factory=list)
    intent_relations: list[str] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    chunk_scores: list[tuple[str, float]] = field(default_factory=list)
    entity_scores: dict[str, float] = field(default_factory=dict)
    paths: list[list[str]] = field(default_factory=list)  # listes d'identifiants de faits
    nodes: dict[str, dict] = field(default_factory=dict)


def detect_intent(question: str) -> list[str]:
    q = normalize_key(question)
    relations: list[str] = []
    for pattern, rels in INTENT_CUES:
        if re.search(pattern, q):
            relations += [r for r in rels if r not in relations]
    return relations


def intent_groups(question: str) -> int:
    """Nombre de familles d'indices relationnels distinctes présentes dans la question."""
    q = normalize_key(question)
    return sum(1 for pattern, _ in INTENT_CUES if re.search(pattern, q))


def personalized_pagerank(nodes: list[str], edges: list[tuple[str, str, float]], seeds: list[str],
                          alpha: float = ALPHA, iterations: int = 40) -> dict[str, float]:
    index = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    if n == 0:
        return {}
    weights = np.zeros((n, n), dtype=np.float64)
    for a, b, w in edges:
        if a in index and b in index:
            weights[index[a], index[b]] += w
            weights[index[b], index[a]] += w  # graphe traité comme non orienté
    out = weights.sum(axis=1, keepdims=True)
    out[out == 0] = 1.0
    transition = weights / out
    restart = np.zeros(n)
    seed_idx = [index[s] for s in seeds if s in index]
    if not seed_idx:
        return {}
    restart[seed_idx] = 1.0 / len(seed_idx)
    p = restart.copy()
    for _ in range(iterations):
        p = alpha * restart + (1 - alpha) * (transition.T @ p)
    return {node: float(p[i]) for node, i in index.items()}


class GraphRetriever:
    def __init__(self, client: Neo4jClient, linker: EntityLinker, max_hops: int = 2) -> None:
        self.client = client
        self.linker = linker
        self.max_hops = max_hops

    # ------------------------------------------------------------------
    def link_question(self, question: str) -> tuple[list[dict], list[dict]]:
        seeds, ambiguous = [], []
        for m in self.linker.find_mentions(question):
            if m.entity_id:
                seeds.append({"id": m.entity_id, "surface": m.surface, "type": m.entity_type})
            elif self.linker.resolver.is_ambiguous_surface(m.surface):
                alias = next(a for a in self.linker.ref.ambiguous if normalize_key(a.surface) == normalize_key(m.surface))
                options = [{"id": cid, "name": self.linker.ref.name(cid), "type": self.linker.ref.entities[cid].type}
                           for cid, _ in alias.candidates]
                ambiguous.append({"surface": m.surface, "candidates": options})
                seeds += [{"id": o["id"], "surface": m.surface, "type": o["type"], "ambiguous": True} for o in options]
        unique: dict[str, dict] = {}
        for s in seeds:
            unique.setdefault(s["id"], s)
        return list(unique.values()), ambiguous

    def retrieve(self, question: str, allowed: list[str], *, max_hops: int | None = None, top_facts: int = 15,
                 top_chunks: int = 20, extra_seeds: list[str] | None = None) -> GraphRetrieval:
        seeds, ambiguous = self.link_question(question)
        for extra in extra_seeds or []:
            if extra not in {s["id"] for s in seeds}:
                seeds.append({"id": extra, "surface": "", "type": None, "expanded": True})
        result = GraphRetrieval(seeds=seeds, ambiguous=ambiguous, intent_relations=detect_intent(question))
        if not seeds:
            return result
        hops = max_hops or self.max_hops
        types = list(TRAVERSAL)
        if any(s.get("type") == "Domain" for s in seeds):
            types.append("BELONGS_TO")

        # Sous-graphe local : relations visibles à 1 saut des graines, puis (si hops = 2) à 1 saut
        # de ce premier voisinage. L'expansion par niveaux donne exactement l'ensemble des relations
        # des chemins de longueur <= 2, sans énumérer les chemins ni tronquer arbitrairement.
        visible = "type(r) IN $types AND (r.source = 'referential' OR any(d IN r.source_doc_ids WHERE d IN $allowed))"
        rows = self.client.read(
            f"""MATCH (s:Entity) WHERE s.id IN $seeds
                OPTIONAL MATCH (s)-[r]-(n:Entity) WHERE {visible}
                WITH collect(DISTINCT r) AS level1, collect(DISTINCT n) AS frontier
                CALL (frontier) {{
                    UNWIND CASE WHEN $hops > 1 THEN frontier ELSE [] END AS f
                    MATCH (f)-[r]-(:Entity) WHERE {visible}
                    RETURN collect(DISTINCT r) AS level2
                }}
                UNWIND level1 + level2 AS r
                WITH DISTINCT r
                WITH r, startNode(r) AS a, endNode(r) AS b
                RETURN a.id AS s, a.name AS s_name, a.type AS s_type, type(r) AS rel, b.id AS o, b.name AS o_name,
                       b.type AS o_type, coalesce(r.roles, []) AS roles, coalesce(r.confidence, 0.7) AS conf,
                       coalesce(r.source_doc_ids, []) AS docs, coalesce(r.evidence_chunk_ids, []) AS chunks,
                       coalesce(r.evidence_quotes, []) AS quotes, r.source AS source
                ORDER BY s, rel, o""",
            seeds=[s["id"] for s in seeds], types=types, allowed=allowed, hops=int(hops))
        if not rows:
            return result

        intent = set(result.intent_relations)
        nodes: dict[str, dict] = {}
        edges: list[tuple[str, str, float]] = []
        facts: list[Fact] = []
        allowed_set = set(allowed)
        for i, row in enumerate(rows):
            nodes[row["s"]] = {"id": row["s"], "name": row["s_name"], "type": row["s_type"]}
            nodes[row["o"]] = {"id": row["o"], "name": row["o_name"], "type": row["o_type"]}
            weight = float(row["conf"]) * (3.0 if row["rel"] in intent else 1.0)
            edges.append((row["s"], row["o"], weight))
            # Seules les preuves issues de documents autorisés sont exposées.
            keep = [j for j, c in enumerate(row["chunks"]) if c.split("#")[0] in allowed_set]
            facts.append(Fact(
                id=f"f{i}", subject_id=row["s"], subject_name=row["s_name"], subject_type=row["s_type"],
                relation=row["rel"], object_id=row["o"], object_name=row["o_name"], object_type=row["o_type"],
                roles=list(row["roles"]), confidence=float(row["conf"]),
                source_doc_ids=[d for d in row["docs"] if d in allowed_set],
                evidence_chunk_ids=[row["chunks"][j] for j in keep],
                evidence_quotes=[row["quotes"][j] for j in keep if j < len(row["quotes"])]))

        seed_ids = [s["id"] for s in seeds]
        # Scores arrondis : l'ordre de sommation flottante ne doit pas départager des ex æquo.
        ppr = {k: round(v, 10) for k, v in personalized_pagerank(sorted(nodes), edges, seed_ids).items()}
        result.entity_scores = ppr
        result.nodes = nodes
        for fact in facts:
            bonus = 3.0 if fact.relation in intent else 1.0
            fact.score = round((ppr.get(fact.subject_id, 0) + ppr.get(fact.object_id, 0)) * bonus * fact.confidence, 10)
        facts.sort(key=lambda f: (-f.score, f.subject_id, f.relation, f.object_id))
        result.facts = facts[:top_facts]
        for idx, fact in enumerate(result.facts, start=1):
            fact.id = f"F{idx}"

        # Passages : preuves des faits retenus + passages mentionnant les entités importantes.
        chunk_scores: dict[str, float] = defaultdict(float)
        for fact in result.facts:
            for chunk_id in fact.evidence_chunk_ids:
                chunk_scores[chunk_id] += fact.score
        top_entities = sorted((e for e in ppr if e not in seed_ids or len(seed_ids) == 1),
                              key=lambda e: (-ppr[e], e))[:12]
        if top_entities:
            mention_rows = self.client.read(
                """MATCH (c:Chunk)-[:MENTIONS]->(e:Entity) WHERE e.id IN $ids AND c.doc_id IN $allowed
                   RETURN c.id AS chunk, collect(e.id) AS entities""", ids=top_entities, allowed=allowed)
            for row in mention_rows:
                chunk_scores[row["chunk"]] += 0.5 * sum(ppr.get(e, 0.0) for e in row["entities"])
        result.chunk_scores = sorted(((c, round(v, 10)) for c, v in chunk_scores.items()),
                                     key=lambda kv: (-kv[1], kv[0]))[:top_chunks]
        result.paths = self._paths(result.facts, seed_ids)
        return result

    @staticmethod
    def _paths(facts: list[Fact], seeds: list[str], max_len: int = 3) -> list[list[str]]:
        """Plus courts chemins (en faits retenus) des graines vers les autres entités."""
        adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for fact in facts:
            adjacency[fact.subject_id].append((fact.object_id, fact.id))
            adjacency[fact.object_id].append((fact.subject_id, fact.id))
        paths: list[list[str]] = []
        seen_targets: set[str] = set()
        for seed in seeds:
            queue: deque[tuple[str, list[str]]] = deque([(seed, [])])
            visited = {seed}
            while queue:
                node, path = queue.popleft()
                if path and node not in seeds and node not in seen_targets:
                    paths.append(path)
                    seen_targets.add(node)
                if len(path) >= max_len:
                    continue
                for neighbour, fact_id in adjacency.get(node, []):
                    if neighbour not in visited:
                        visited.add(neighbour)
                        queue.append((neighbour, path + [fact_id]))
        return paths[:12]
