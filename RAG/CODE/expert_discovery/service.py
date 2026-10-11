"""Recherche d'experts transparente et sensible aux droits d'accès.

Score d'une personne p pour un domaine D :

    score(p, D) = Σ_type  poids(type) × récence(meilleure preuve) × (1 + 0,25 × documents supplémentaires)

où les types de preuves sont : expertise déclarée, pilotage/participation/parrainage d'un projet
du domaine, propriété d'une procédure du domaine, responsabilité d'une application du domaine,
rédaction d'un document du domaine, co-mention (plafonnée). La récence décroît de moitié tous les
`half_life_years` ans par rapport à la date de référence.

Chaque résultat expose ses preuves (type, document, date, citation) : le classement est
explicable et contestable. Seuls les documents accessibles à l'utilisateur sont exploités.
La baseline `mention_count` (nombre de passages citant la personne avec un élément du domaine)
sert de point de comparaison expérimental.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from core.settings import CODE_DIR
from extraction.linker import EntityLinker
from knowledge_graph.client import Neo4jClient

LIMITS = ("Classement fondé uniquement sur les documents accessibles à l'utilisateur. Les expertises "
          "déclarées sont reprises telles qu'écrites dans les documents ; une mention n'équivaut pas à une "
          "expertise démontrée. À utiliser comme aide à l'orientation, jamais comme évaluation des personnes.")


@dataclass
class Evidence:
    kind: str
    label: str
    doc_id: str
    doc_title: str
    doc_date: str | None
    quote: str | None
    weight: float


@dataclass
class ExpertResult:
    person_id: str
    name: str
    score: float
    confidence: str
    evidence: list[Evidence] = field(default_factory=list)
    mention_count: int = 0

    @property
    def justification(self) -> str:
        kinds = []
        for ev in sorted(self.evidence, key=lambda e: -e.weight):
            if ev.label not in kinds:
                kinds.append(ev.label)
        return "; ".join(kinds[:4])


class ExpertService:
    def __init__(self, client: Neo4jClient, linker: EntityLinker, reference_date: date,
                 weights_path: Path | None = None) -> None:
        self.client = client
        self.linker = linker
        self.reference_date = reference_date
        config = yaml.safe_load((weights_path or CODE_DIR / "config" / "expert_weights.yaml").read_text(encoding="utf-8"))
        self.w = config["weights"]
        self.half_life = float(config["recency"]["half_life_years"])
        self.extra_bonus = float(config["repetition"]["extra_document_bonus"])
        self.max_extra = int(config["repetition"]["max_extra_documents"])

    # ------------------------------------------------------------------
    def resolve_domain(self, text: str) -> str | None:
        if text.startswith("dom:"):
            return text
        for m in self.linker.find_mentions(text):
            if m.entity_type == "Domain" and m.entity_id:
                return m.entity_id
            if m.entity_type == "Concept" and m.entity_id:
                concept = self.linker.ref.get(m.entity_id)
                if concept and concept.domain:
                    return concept.domain
        resolution = self.linker.resolver.resolve(text, "Domain", context=text)
        return resolution.entity_id

    def domains(self, allowed: list[str]) -> list[dict]:
        rows = self.client.read(
            """MATCH (d:Domain)
               OPTIONAL MATCH (p:Person)-[r:HAS_EXPERTISE]->(d) WHERE any(x IN r.source_doc_ids WHERE x IN $allowed)
               RETURN d.id AS id, d.name AS name, count(DISTINCT p) AS declared_experts ORDER BY d.name""",
            allowed=allowed)
        return rows

    def _recency(self, doc_date: str | None) -> float:
        if not doc_date:
            return 0.5
        try:
            d = date.fromisoformat(doc_date[:10])
        except ValueError:
            return 0.5
        age_years = max(0.0, (self.reference_date - d).days / 365.25)
        return 0.5 ** (age_years / self.half_life)

    def _documents(self, allowed: list[str]) -> dict[str, dict]:
        rows = self.client.read("MATCH (d:Document) WHERE d.id IN $allowed RETURN d.id AS id, d.title AS title, "
                                "toString(d.doc_date) AS date, d.doc_type AS type", allowed=allowed)
        return {r["id"]: r for r in rows}

    def find_experts(self, domain_id: str, allowed: list[str], limit: int = 10) -> list[ExpertResult]:
        docs = self._documents(allowed)
        raw: list[tuple[str, str, str, str, list[str], list[str], list[str], list[str]]] = []

        def collect(query: str, kind_from_row) -> None:
            for row in self.client.read(query, dom=domain_id, allowed=allowed):
                kind, label = kind_from_row(row)
                if kind:
                    raw.append((row["pid"], row["pname"], kind, label, row["docs"], row.get("chunks") or [],
                                row.get("quotes") or [], row.get("roles") or []))

        collect("""MATCH (p:Person)-[r:HAS_EXPERTISE]->(:Domain {id: $dom})
                   WHERE p.status = 'validated'
                   RETURN p.id AS pid, p.name AS pname, [x IN r.source_doc_ids WHERE x IN $allowed] AS docs,
                          r.evidence_chunk_ids AS chunks, r.evidence_quotes AS quotes""",
                lambda r: ("declared_expertise", "expertise déclarée dans les documents"))
        for row in self.client.read(
                """MATCH (p:Person)-[r:PARTICIPATES_IN]->(j:Project)-[:BELONGS_TO]->(:Domain {id: $dom})
                   WHERE p.status = 'validated'
                   RETURN p.id AS pid, p.name AS pname, j.name AS project, r.roles AS roles,
                          [x IN r.source_doc_ids WHERE x IN $allowed] AS docs, r.evidence_chunk_ids AS chunks,
                          r.evidence_quotes AS quotes""", dom=domain_id, allowed=allowed):
            for role, kind, label in [("lead", "project_lead", "pilote du projet"),
                                      ("member", "project_member", "membre du projet"),
                                      ("sponsor", "project_sponsor", "sponsor du projet")]:
                if role in (row["roles"] or []):
                    raw.append((row["pid"], row["pname"], kind, f"{label} {row['project']}", row["docs"],
                                row["chunks"] or [], row["quotes"] or [], []))
        for row in self.client.read(
                """MATCH (p:Person)-[r:RESPONSIBLE_FOR]->(x:Procedure)-[:BELONGS_TO]->(:Domain {id: $dom})
                   WHERE p.status = 'validated'
                   RETURN p.id AS pid, p.name AS pname, x.name AS target,
                          [x IN r.source_doc_ids WHERE x IN $allowed] AS docs, r.evidence_chunk_ids AS chunks,
                          r.evidence_quotes AS quotes""", dom=domain_id, allowed=allowed):
            raw.append((row["pid"], row["pname"], "procedure_owner", f"propriétaire de la procédure « {row['target']} »",
                        row["docs"], row["chunks"] or [], row["quotes"] or [], []))
        for row in self.client.read(
                """MATCH (p:Person)-[r:RESPONSIBLE_FOR]->(s:System)
                   WHERE p.status = 'validated' AND (
                         EXISTS { MATCH (x:Procedure)-[:USES]->(s) WHERE (x)-[:BELONGS_TO]->(:Domain {id: $dom}) }
                      OR EXISTS { MATCH (j:Project)-[:DELIVERS]->(s) WHERE (j)-[:BELONGS_TO]->(:Domain {id: $dom}) })
                   RETURN p.id AS pid, p.name AS pname, s.name AS target,
                          [x IN r.source_doc_ids WHERE x IN $allowed] AS docs, r.evidence_chunk_ids AS chunks,
                          r.evidence_quotes AS quotes""", dom=domain_id, allowed=allowed):
            raw.append((row["pid"], row["pname"], "system_owner", f"responsable de l'application {row['target']}",
                        row["docs"], row["chunks"] or [], row["quotes"] or [], []))
        for row in self.client.read(
                """MATCH (d:Document)-[:AUTHORED_BY]->(p:Person), (d)-[:DESCRIBES]->(x)-[:BELONGS_TO]->(:Domain {id: $dom})
                   WHERE d.id IN $allowed AND p.status = 'validated'
                   RETURN p.id AS pid, p.name AS pname, collect(DISTINCT d.id) AS docs""", dom=domain_id,
                allowed=allowed):
            raw.append((row["pid"], row["pname"], "authored_document", "rédacteur de documents du domaine",
                        row["docs"], [], [], []))

        mention_rows = self.client.read(
            """MATCH (d:Domain {id: $dom})
               OPTIONAL MATCH (t:Entity)-[:BELONGS_TO]->(d)
               WITH d, collect(t.id) + [d.id] AS targets
               MATCH (c:Chunk)-[:MENTIONS]->(p:Person), (c)-[:MENTIONS]->(t:Entity)
               WHERE t.id IN targets AND c.doc_id IN $allowed AND p.status = 'validated'
               RETURN p.id AS pid, p.name AS pname, count(DISTINCT c) AS n, collect(DISTINCT c.doc_id) AS docs""",
            dom=domain_id, allowed=allowed)

        results: dict[str, ExpertResult] = {}
        for pid, pname, kind, label, doc_ids, chunks, quotes, _ in raw:
            doc_ids = [d for d in doc_ids if d in docs]
            if not doc_ids:
                continue
            best_doc = max(doc_ids, key=lambda d: self._recency(docs[d]["date"]))
            weight = float(self.w[kind])
            if kind == "declared_expertise" and any(docs[d]["type"] == "referentiel_rh" for d in doc_ids):
                weight += float(self.w["validated_skill_bonus"])
            weight *= self._recency(docs[best_doc]["date"])
            weight *= 1 + self.extra_bonus * min(len(doc_ids) - 1, self.max_extra)
            quote = next((q for c, q in zip(chunks, quotes, strict=False) if c.split("#")[0] == best_doc), None)
            result = results.setdefault(pid, ExpertResult(person_id=pid, name=pname, score=0.0, confidence="faible"))
            result.evidence.append(Evidence(kind=kind, label=label, doc_id=best_doc, doc_title=docs[best_doc]["title"],
                                            doc_date=docs[best_doc]["date"], quote=quote, weight=round(weight, 3)))
        for row in mention_rows:
            result = results.setdefault(row["pid"], ExpertResult(person_id=row["pid"], name=row["pname"], score=0.0,
                                                                 confidence="faible"))
            result.mention_count = int(row["n"])
            weight = min(float(self.w["co_mention"]) * row["n"], float(self.w["co_mention_cap"]))
            result.evidence.append(Evidence(kind="co_mention", label=f"cité dans {row['n']} passage(s) du domaine",
                                            doc_id=row["docs"][0], doc_title=docs.get(row["docs"][0], {}).get("title", ""),
                                            doc_date=None, quote=None, weight=round(weight, 3)))
        for result in results.values():
            result.score = round(sum(e.weight for e in result.evidence), 3)
            kinds = {e.kind for e in result.evidence}
            strong = kinds & {"project_lead", "procedure_owner", "project_member", "system_owner"}
            if "declared_expertise" in kinds and strong:
                result.confidence = "élevée"
            elif "declared_expertise" in kinds or len(strong) >= 2:
                result.confidence = "moyenne"
        ranked = sorted((r for r in results.values() if r.score > 0), key=lambda r: (-r.score, r.name))
        return ranked[:limit]

    def mention_baseline(self, domain_id: str, allowed: list[str], limit: int = 10) -> list[tuple[str, int]]:
        rows = self.client.read(
            """MATCH (d:Domain {id: $dom})
               OPTIONAL MATCH (t:Entity)-[:BELONGS_TO]->(d)
               WITH d, collect(t.id) + [d.id] AS targets
               MATCH (c:Chunk)-[:MENTIONS]->(p:Person), (c)-[:MENTIONS]->(t:Entity)
               WHERE t.id IN targets AND c.doc_id IN $allowed
               RETURN p.id AS pid, count(DISTINCT c) AS n ORDER BY n DESC, pid LIMIT $limit""",
            dom=domain_id, allowed=allowed, limit=limit)
        return [(r["pid"], int(r["n"])) for r in rows]
