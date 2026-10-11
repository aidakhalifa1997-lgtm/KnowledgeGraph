"""Écriture et maintenance du Knowledge Graph.

Principes :
- **Idempotence** : réingérer un document identique ne crée aucun doublon (MERGE sur des
  identifiants stables ; le contenu d'un document est détaché avant d'être réécrit).
- **Provenance** : chaque relation sémantique conserve des listes alignées — documents
  sources, passages sources, citations, rôles, confiance et extracteur de chaque preuve.
  Les agrégats (rôles, confiance, extracteurs) sont recalculés à partir de ces preuves.
- **Pas de relation obsolète** : à la modification ou à la suppression d'un document, ses
  preuves sont retirées des relations ; une relation sans preuve restante est supprimée.
- **Cohérence des versions** : les documents de même référence sont ordonnés par version ;
  le plus récent est `active`, les autres `superseded` (relation SUPERSEDES).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

import numpy as np

from core.models import DocumentRecord, IngestionReport
from extraction.referential import Referential
from ingestion.processor import ProcessedDocument
from knowledge_graph.client import Neo4jClient
from knowledge_graph.schema import ENTITY_LABELS, SEMANTIC_RELATIONS, VECTOR_INDEX, schema_statements

logger = logging.getLogger(__name__)

SEARCHABLE_STATUSES = ["active", "superseded"]

# Recalcul des agrégats d'une relation à partir de ses preuves alignées.
_AGGREGATES = """
SET r.roles = reduce(acc = [], s IN r.evidence_roles |
                     acc + [x IN split(s, ',') WHERE x <> '' AND NOT x IN acc]),
    r.confidence = reduce(m = 0.0, c IN r.evidence_conf | CASE WHEN c > m THEN c ELSE m END),
    r.extractors = reduce(acc = [], s IN r.evidence_extractors |
                          acc + [x IN split(s, '+') WHERE NOT x IN acc])
"""


def _version_key(version: str | None) -> tuple:
    if not version:
        return (0,)
    return tuple(int(x) for x in re.findall(r"\d+", version)) or (0,)


class GraphRepository:
    def __init__(self, client: Neo4jClient, referential: Referential) -> None:
        self.client = client
        self.ref = referential

    # ------------------------------------------------------------------ schéma
    def ensure_schema(self, embedding_dim: int) -> None:
        current = self.vector_index_dimension()
        if current is not None and current != embedding_dim:
            logger.warning("Dimension de l'index vectoriel différente : recréation",
                           extra={"old": current, "new": embedding_dim})
            self.client.write(f"DROP INDEX {VECTOR_INDEX} IF EXISTS")
            self.client.write("MATCH (c:Chunk) REMOVE c.embedding")
        for statement in schema_statements(embedding_dim):
            self.client.write(statement)
        self.client.write("CALL db.awaitIndexes(120)")
        self.ensure_taxonomy()

    def vector_index_dimension(self) -> int | None:
        rows = self.client.read("SHOW VECTOR INDEXES YIELD name, options WHERE name = $name RETURN options",
                                name=VECTOR_INDEX)
        if not rows:
            return None
        return int(rows[0]["options"]["indexConfig"]["vector.dimensions"])

    def reset(self) -> None:
        """Supprime tout le contenu (utilisé pour les tests et la reconstruction complète)."""
        self.client.write("MATCH (n) DETACH DELETE n")
        self.ensure_taxonomy()

    def ensure_taxonomy(self) -> None:
        rows = [{"id": d.id, "name": d.name, "aliases": d.aliases} for d in self.ref.by_type("Domain")]
        self.client.write(
            """UNWIND $rows AS row
               MERGE (e:Entity:Domain {id: row.id})
               SET e.name = row.name, e.type = 'Domain', e.aliases = row.aliases,
                   e.aliases_text = reduce(t = '', a IN row.aliases | t + ' ' + a),
                   e.status = 'validated', e.source = 'referential'""", rows=rows)

    # ------------------------------------------------------------------ lecture d'état
    def get_document_state(self, doc_id: str) -> dict | None:
        rows = self.client.read("MATCH (d:Document {id: $id}) RETURN d.content_hash AS hash, d.status AS status, "
                                "d.file_name AS file_name", id=doc_id)
        return rows[0] if rows else None

    def find_by_hash(self, content_hash: str, exclude_id: str) -> dict | None:
        rows = self.client.read(
            "MATCH (d:Document {content_hash: $h}) WHERE d.id <> $id AND d.status IN $statuses "
            "RETURN d.id AS id, d.file_name AS file_name ORDER BY d.file_name LIMIT 1",
            h=content_hash, id=exclude_id, statuses=SEARCHABLE_STATUSES)
        return rows[0] if rows else None

    def signatures(self) -> list[dict]:
        return self.client.read(
            "MATCH (d:Document) WHERE d.status IN $statuses AND d.minhash IS NOT NULL "
            "RETURN d.id AS id, d.file_name AS file_name, d.reference AS reference, d.version AS version, "
            "d.minhash AS minhash, d.draft_marker AS draft_marker", statuses=SEARCHABLE_STATUSES)

    def documents_from_source(self, source_dir: str) -> list[dict]:
        return self.client.read("MATCH (d:Document) WHERE d.source_path STARTS WITH $dir "
                                "RETURN d.id AS id, d.file_name AS file_name, d.source_path AS path", dir=source_dir)

    # ------------------------------------------------------------------ écriture
    def _document_props(self, record: DocumentRecord, minhash: list[int] | None, draft_marker: bool) -> dict:
        return {
            "id": record.id, "file_name": record.file_name, "source_path": record.source_path,
            "format": record.format, "content_hash": record.content_hash, "size_bytes": record.size_bytes,
            "title": record.title, "reference": record.reference, "version": record.version,
            "doc_date": record.doc_date.isoformat() if record.doc_date else None, "doc_type": record.doc_type,
            "department_name": record.department_name, "author_name": record.author_name,
            "classification": record.classification, "diffusion": record.diffusion, "pages": record.pages,
            "ocr_used": record.ocr_used, "ocr_confidence": record.ocr_confidence, "language": record.language,
            "quality_score": record.quality_score, "status": record.status,
            "issues": json.dumps([i.model_dump() for i in record.issues], ensure_ascii=False),
            "minhash": minhash, "draft_marker": draft_marker,
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }

    @staticmethod
    def _detach_content(tx, doc_id: str) -> None:
        """Retire tout ce qu'un document a apporté au graphe (passages, mentions, preuves)."""
        tx.run("MATCH (c:Chunk {doc_id: $id}) DETACH DELETE c", id=doc_id)
        tx.run(
            """MATCH ()-[r]->() WHERE r.source = 'extracted' AND $id IN r.source_doc_ids
               WITH r, [i IN range(0, size(r.evidence_chunk_ids) - 1)
                        WHERE NOT r.evidence_chunk_ids[i] STARTS WITH $prefix] AS keep
               SET r.evidence_chunk_ids = [i IN keep | r.evidence_chunk_ids[i]],
                   r.evidence_quotes = [i IN keep | r.evidence_quotes[i]],
                   r.evidence_roles = [i IN keep | r.evidence_roles[i]],
                   r.evidence_conf = [i IN keep | r.evidence_conf[i]],
                   r.evidence_extractors = [i IN keep | r.evidence_extractors[i]],
                   r.source_doc_ids = [d IN r.source_doc_ids WHERE d <> $id]
               WITH r
            """ + _AGGREGATES, id=doc_id, prefix=f"{doc_id}#")
        tx.run("MATCH ()-[r]->() WHERE r.source = 'extracted' AND size(r.source_doc_ids) = 0 DELETE r")
        tx.run("MATCH (d:Document {id: $id})-[r:DESCRIBES|AUTHORED_BY|ISSUED_BY|SUPERSEDES|DUPLICATE_OF|SIMILAR_TO]-() "
               "DELETE r", id=doc_id)

    def _merge_entities(self, tx, entity_ids: set[str]) -> None:
        by_label: dict[str, list[dict]] = {}
        for entity_id in entity_ids:
            entity = self.ref.get(entity_id)
            if entity is None or entity.type not in ENTITY_LABELS:
                continue
            by_label.setdefault(entity.type, []).append({
                "id": entity.id, "name": entity.name, "aliases": entity.aliases,
                "aliases_text": " ".join(entity.aliases)})
        for label, rows in by_label.items():
            # L'étiquette provient d'une liste blanche (ENTITY_LABELS) : pas d'injection possible.
            tx.run(f"""UNWIND $rows AS row
                       MERGE (e:Entity {{id: row.id}})
                       SET e:{label}, e.type = '{label}', e.name = row.name, e.aliases = row.aliases,
                           e.aliases_text = row.aliases_text, e.status = 'validated', e.source = 'referential'""",
                   rows=rows)

    def write_document(self, processed: ProcessedDocument, embeddings: np.ndarray, draft_marker: bool = False) -> None:
        record = processed.record
        props = self._document_props(record, processed.minhash, draft_marker)
        chunks = []
        for chunk, vector in zip(processed.chunks, embeddings, strict=True):
            from ingestion.chunking import contextual_text

            chunks.append({
                "id": chunk.id, "doc_id": chunk.doc_id, "index": chunk.index, "text": chunk.text,
                "section": chunk.section, "page": chunk.page, "char_start": chunk.char_start,
                "char_end": chunk.char_end, "search_text": contextual_text(record.title, chunk.section, chunk.text),
                "embedding": [float(x) for x in vector],
            })
        mention_rows: dict[tuple[str, str], dict] = {}
        for chunk_id, mentions in processed.mentions.items():
            for m in mentions:
                if not m.entity_id:
                    continue
                row = mention_rows.setdefault((chunk_id, m.entity_id), {
                    "chunk": chunk_id, "entity": m.entity_id, "surfaces": [], "method": m.method, "conf": m.confidence,
                    "count": 0})
                row["count"] += 1
                if m.surface not in row["surfaces"]:
                    row["surfaces"].append(m.surface)
        entity_ids = {r["entity"] for r in mention_rows.values()}
        entity_ids |= {r.subject_id for r in processed.relations} | {r.object_id for r in processed.relations}
        entity_ids |= set(record.describes)
        entity_ids |= {x for x in (record.author_id, record.department_id) if x}

        relations_by_type: dict[str, list[dict]] = {}
        for rel in processed.relations:
            relations_by_type.setdefault(rel.relation, []).append({
                "s": rel.subject_id, "o": rel.object_id, "doc": rel.doc_id, "chunk": rel.chunk_id,
                "quote": rel.evidence, "roles": ",".join(rel.roles), "conf": float(rel.confidence),
                "extractor": rel.extractor})

        def work(tx) -> None:
            self._detach_content(tx, record.id)
            tx.run("MERGE (d:Document {id: $p.id}) SET d += $p, d.doc_date = CASE WHEN $p.doc_date IS NULL THEN null "
                   "ELSE date($p.doc_date) END", p=props)
            self._merge_entities(tx, entity_ids)
            tx.run("""UNWIND $rows AS row
                      MATCH (d:Document {id: row.doc_id})
                      CREATE (c:Chunk {id: row.id, doc_id: row.doc_id, index: row.index, text: row.text,
                                       section: row.section, page: row.page, char_start: row.char_start,
                                       char_end: row.char_end, search_text: row.search_text})
                      SET c.embedding = row.embedding
                      CREATE (c)-[:PART_OF]->(d)""", rows=chunks)
            tx.run("""MATCH (c:Chunk {doc_id: $id}) WITH c ORDER BY c.index
                      WITH collect(c) AS cs
                      UNWIND range(0, size(cs) - 2) AS i
                      WITH cs[i] AS a, cs[i + 1] AS b
                      CREATE (a)-[:NEXT]->(b)""", id=record.id)
            tx.run("""UNWIND $rows AS row
                      MATCH (c:Chunk {id: row.chunk}), (e:Entity {id: row.entity})
                      MERGE (c)-[m:MENTIONS]->(e)
                      SET m.surfaces = row.surfaces, m.method = row.method, m.confidence = row.conf,
                          m.count = row.count""", rows=list(mention_rows.values()))
            for candidate in processed.candidates:
                tx.run("""MERGE (e:Entity {id: $c.id})
                          ON CREATE SET e:Person, e.type = 'Person', e.name = $c.name, e.aliases = [],
                                        e.aliases_text = '', e.status = 'candidate', e.source = 'extracted'
                          SET e.possible_match = $c.possible_match, e.match_score = $c.match_score
                          WITH e
                          MATCH (ch:Chunk {id: $c.chunk_id})
                          MERGE (ch)-[m:MENTIONS]->(e) SET m.surfaces = [$c.surface], m.method = 'ner',
                                m.confidence = 0.5, m.count = 1""", c=candidate.model_dump())
            for relation, rows in relations_by_type.items():
                if relation not in SEMANTIC_RELATIONS:
                    continue
                tx.run(f"""UNWIND $rows AS row
                           MATCH (s:Entity {{id: row.s}}), (o:Entity {{id: row.o}})
                           MERGE (s)-[r:{relation}]->(o)
                           ON CREATE SET r.source = 'extracted', r.first_seen = datetime(), r.source_doc_ids = [],
                                         r.evidence_chunk_ids = [], r.evidence_quotes = [], r.evidence_roles = [],
                                         r.evidence_conf = [], r.evidence_extractors = []
                           SET r.source_doc_ids = CASE WHEN row.doc IN r.source_doc_ids THEN r.source_doc_ids
                                                       ELSE r.source_doc_ids + row.doc END,
                               r.evidence_chunk_ids = r.evidence_chunk_ids + row.chunk,
                               r.evidence_quotes = r.evidence_quotes + row.quote,
                               r.evidence_roles = r.evidence_roles + row.roles,
                               r.evidence_conf = r.evidence_conf + row.conf,
                               r.evidence_extractors = r.evidence_extractors + row.extractor,
                               r.last_seen = datetime()
                           WITH r
                           {_AGGREGATES}""", rows=rows)
            meta_links = [("DESCRIBES", e) for e in record.describes]
            if record.author_id:
                meta_links.append(("AUTHORED_BY", record.author_id))
            if record.department_id:
                meta_links.append(("ISSUED_BY", record.department_id))
            for rel_type, target in meta_links:
                tx.run(f"MATCH (d:Document {{id: $d}}), (e:Entity {{id: $e}}) MERGE (d)-[:{rel_type}]->(e)",
                       d=record.id, e=target)

        with self.client.session() as session:
            session.execute_write(work)

    def write_shell(self, record: DocumentRecord, draft_marker: bool = False, duplicate_of: str | None = None,
                    minhash: list[int] | None = None) -> None:
        """Document sans contenu exploitable (rejeté, en quarantaine ou doublon) : tracé, non indexé."""
        props = self._document_props(record, minhash if record.status != "duplicate" else None, draft_marker)

        def work(tx) -> None:
            self._detach_content(tx, record.id)
            tx.run("MERGE (d:Document {id: $p.id}) SET d += $p, d.doc_date = CASE WHEN $p.doc_date IS NULL THEN null "
                   "ELSE date($p.doc_date) END", p=props)
            if duplicate_of:
                tx.run("MATCH (d:Document {id: $a}), (o:Document {id: $b}) MERGE (d)-[:DUPLICATE_OF]->(o)",
                       a=record.id, b=duplicate_of)

        with self.client.session() as session:
            session.execute_write(work)

    def mark_duplicate(self, doc_id: str, duplicate_of: str) -> None:
        def work(tx) -> None:
            self._detach_content(tx, doc_id)
            tx.run("MATCH (d:Document {id: $a}), (o:Document {id: $b}) SET d.status = 'duplicate', d.minhash = null "
                   "MERGE (d)-[:DUPLICATE_OF]->(o)", a=doc_id, b=duplicate_of)

        with self.client.session() as session:
            session.execute_write(work)

    def delete_document(self, doc_id: str) -> bool:
        def work(tx) -> bool:
            exists = tx.run("MATCH (d:Document {id: $id}) RETURN count(d) AS n", id=doc_id).single()["n"]
            if not exists:
                return False
            self._detach_content(tx, doc_id)
            tx.run("MATCH (d:Document {id: $id}) DETACH DELETE d", id=doc_id)
            return True

        with self.client.session() as session:
            deleted = session.execute_write(work)
        return deleted

    # ------------------------------------------------------------------ post-traitements
    def update_versions(self) -> int:
        rows = self.client.read(
            "MATCH (d:Document) WHERE d.status IN $statuses AND d.reference IS NOT NULL "
            "RETURN d.reference AS ref, collect({id: d.id, version: d.version, date: toString(d.doc_date)}) AS docs",
            statuses=SEARCHABLE_STATUSES)
        changes = 0
        for row in rows:
            docs = sorted(row["docs"], key=lambda d: (_version_key(d["version"]), d["date"] or ""), reverse=True)
            ids = [d["id"] for d in docs]
            self.client.write("MATCH (a:Document)-[r:SUPERSEDES]->(b:Document) WHERE a.id IN $ids OR b.id IN $ids "
                              "DELETE r", ids=ids)
            self.client.write("MATCH (d:Document {id: $id}) SET d.status = 'active', d.superseded_by = null", id=ids[0])
            for newer, older in zip(ids, ids[1:], strict=False):
                self.client.write("MATCH (a:Document {id: $a}), (b:Document {id: $b}) "
                                  "SET b.status = 'superseded', b.superseded_by = $a MERGE (a)-[:SUPERSEDES]->(b)",
                                  a=newer, b=older)
                changes += 1
        return changes

    def derive_taxonomy_links(self) -> None:
        rows = [{"id": e.id, "domain": e.domain} for e in self.ref.entities.values()
                if e.domain and e.type in ("Concept", "Procedure", "Project")]
        self.client.write("""UNWIND $rows AS row
                             MATCH (e:Entity {id: row.id}), (d:Domain {id: row.domain})
                             MERGE (e)-[r:BELONGS_TO]->(d) SET r.source = 'referential'""", rows=rows)

    def derive_covers(self) -> None:
        """Règle métier : une procédure/un projet « traite » les concepts mentionnés dans les
        documents qui le décrivent. Relation dérivée (source = rule), recalculée intégralement."""
        self.client.write("MATCH ()-[r:COVERS]->() DELETE r")
        self.client.write(
            """MATCH (d:Document)-[:DESCRIBES]->(x:Entity) WHERE d.status IN $statuses AND (x:Procedure OR x:Project)
               MATCH (d)<-[:PART_OF]-(:Chunk)-[:MENTIONS]->(c:Concept)
               WITH x, c, collect(DISTINCT d.id) AS docs
               MERGE (x)-[r:COVERS]->(c)
               SET r.source = 'rule', r.source_doc_ids = docs""", statuses=SEARCHABLE_STATUSES)

    def compute_similar_to(self, top_k: int = 3) -> None:
        """Similarité de contenu entre documents (centroïde des passages). Relation dérivée,
        stockée pour l'exploration du graphe ; les recommandations la recalculent."""
        rows = self.client.read(
            "MATCH (d:Document)<-[:PART_OF]-(c:Chunk) WHERE d.status IN $statuses AND c.embedding IS NOT NULL "
            "RETURN d.id AS id, collect(c.embedding) AS embs", statuses=SEARCHABLE_STATUSES)
        self.client.write("MATCH ()-[r:SIMILAR_TO]->() DELETE r")
        if len(rows) < 2:
            return
        ids = [r["id"] for r in rows]
        centroids = np.vstack([np.mean(np.asarray(r["embs"], dtype=np.float32), axis=0) for r in rows])
        centroids /= np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-9
        sims = centroids @ centroids.T
        links = []
        for i, doc_id in enumerate(ids):
            order = [j for j in np.argsort(-sims[i]) if j != i][:top_k]
            links += [{"a": doc_id, "b": ids[j], "score": round(float(sims[i, j]), 4)} for j in order]
        self.client.write("""UNWIND $rows AS row
                             MATCH (a:Document {id: row.a}), (b:Document {id: row.b})
                             MERGE (a)-[r:SIMILAR_TO]->(b) SET r.score = row.score, r.derived = true""", rows=links)

    def cleanup_orphans(self) -> int:
        rows = self.client.write(
            """MATCH (e:Entity) WHERE NOT e:Domain AND NOT (e)<-[:MENTIONS]-()
                 AND NOT (e)<-[:DESCRIBES|AUTHORED_BY|ISSUED_BY]-()
               WITH e, e.id AS id DETACH DELETE e RETURN count(id) AS n""")
        return rows[0]["n"] if rows else 0

    def record_run(self, report: IngestionReport) -> None:
        summary = {
            "id": report.run_id, "started_at": report.started_at, "finished_at": report.finished_at,
            "duration_seconds": report.duration_seconds, "files_seen": report.files_seen,
            "ingested": report.count("ingested"), "updated": report.count("updated"),
            "unchanged": report.count("unchanged"), "duplicates": report.count("duplicate"),
            "quarantined": report.count("quarantined"), "rejected": report.count("rejected"),
            "errors": report.count("error"), "deleted": len(report.deleted_documents),
            "details": json.dumps([r.model_dump() for r in report.results], ensure_ascii=False, default=str)[:200000],
        }
        self.client.write("CREATE (r:IngestionRun) SET r = $p", p=summary)
