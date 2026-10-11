"""Requêtes de lecture pour l'exploration du graphe (API et interface).

Règle de visibilité appliquée partout :
- une relation sémantique est visible si au moins un de ses documents sources est autorisé
  (ou si elle provient du référentiel) ;
- une entité est visible si elle est mentionnée dans un passage autorisé, décrite par un
  document autorisé, ou si c'est un domaine (taxonomie publique) ;
- un document est visible s'il figure dans la liste des documents autorisés.
"""

from __future__ import annotations

import re

from core.ontology import ENTITY_TYPES, RELATIONS
from knowledge_graph.client import Neo4jClient
from knowledge_graph.schema import SEMANTIC_RELATIONS

_VISIBLE_REL = "(r.source = 'referential' OR any(d IN coalesce(r.source_doc_ids, []) WHERE d IN $allowed))"
_VISIBLE_ENTITY = ("(e:Domain OR EXISTS { MATCH (c:Chunk)-[:MENTIONS]->(e) WHERE c.doc_id IN $allowed } "
                   "OR EXISTS { MATCH (d:Document)-[:DESCRIBES]->(e) WHERE d.id IN $allowed })")


class GraphQueries:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def schema(self) -> dict:
        return {
            "entity_types": [{"name": k, "description": v} for k, v in ENTITY_TYPES.items()],
            "relation_types": [{"name": r.name, "subjects": sorted(r.subject_types), "objects": sorted(r.object_types),
                                "description": r.description, "derived": not r.extracted} for r in RELATIONS.values()],
        }

    def stats(self, allowed: list[str]) -> dict:
        entities = self.client.read(
            f"MATCH (e:Entity) WHERE {_VISIBLE_ENTITY} RETURN e.type AS type, count(*) AS n ORDER BY n DESC",
            allowed=allowed)
        relations = self.client.read(
            f"MATCH ()-[r]->() WHERE type(r) IN $types AND {_VISIBLE_REL} RETURN type(r) AS type, count(*) AS n "
            "ORDER BY n DESC", types=SEMANTIC_RELATIONS, allowed=allowed)
        documents = self.client.read(
            "MATCH (d:Document) WHERE d.id IN $allowed RETURN d.status AS status, count(*) AS n", allowed=allowed)
        chunks = self.client.read("MATCH (c:Chunk) WHERE c.doc_id IN $allowed RETURN count(c) AS n", allowed=allowed)
        return {"entities": entities, "relations": relations, "documents": documents,
                "chunks": chunks[0]["n"] if chunks else 0}

    def search_entities(self, text: str, allowed: list[str], types: list[str] | None = None, limit: int = 20) -> list[dict]:
        cleaned = re.sub(r'[+\-!(){}\[\]^"~*?:\\/]|&&|\|\|', " ", text).strip().lower()
        if not cleaned:
            return []
        query = " AND ".join(f"{w}*" for w in cleaned.split()[:5])
        return self.client.read(
            f"""CALL db.index.fulltext.queryNodes('entity_name_ft', $q, {{limit: 100}}) YIELD node AS e, score
                WHERE ($types IS NULL OR e.type IN $types) AND {_VISIBLE_ENTITY}
                RETURN e.id AS id, e.name AS name, e.type AS type, e.status AS status, score
                ORDER BY score DESC, id LIMIT $limit""", q=query, types=types, allowed=allowed, limit=limit)

    def entity(self, entity_id: str, allowed: list[str]) -> dict | None:
        rows = self.client.read(
            f"""MATCH (e:Entity {{id: $id}}) WHERE {_VISIBLE_ENTITY}
                OPTIONAL MATCH (c:Chunk)-[:MENTIONS]->(e) WHERE c.doc_id IN $allowed
                WITH e, count(DISTINCT c) AS mentions, collect(DISTINCT c.doc_id)[..10] AS doc_ids
                RETURN e {{.id, .name, .type, .aliases, .status, .source, .possible_match}} AS entity, mentions, doc_ids""",
            id=entity_id, allowed=allowed)
        if not rows:
            return None
        row = rows[0]
        relations = self.client.read(
            f"""MATCH (e:Entity {{id: $id}})-[r]-(o:Entity)
                WHERE type(r) IN $types AND {_VISIBLE_REL}
                RETURN type(r) AS relation, startNode(r).id = e.id AS outgoing, o.id AS other_id, o.name AS other_name,
                       o.type AS other_type, coalesce(r.roles, []) AS roles, r.confidence AS confidence,
                       [d IN coalesce(r.source_doc_ids, []) WHERE d IN $allowed] AS source_doc_ids,
                       [i IN range(0, size(coalesce(r.evidence_chunk_ids, [])) - 1)
                        WHERE split(r.evidence_chunk_ids[i], '#')[0] IN $allowed | r.evidence_quotes[i]][..3] AS quotes,
                       r.source AS source
                ORDER BY relation, other_name""", id=entity_id, types=SEMANTIC_RELATIONS, allowed=allowed)
        documents = self.client.read(
            "MATCH (d:Document) WHERE d.id IN $ids RETURN d.id AS id, d.title AS title, d.doc_type AS doc_type, "
            "d.status AS status", ids=row["doc_ids"])
        return {**row["entity"], "mentions": row["mentions"], "documents": documents, "relations": relations}

    def neighborhood(self, node_id: str, allowed: list[str], depth: int = 1, relation_types: list[str] | None = None,
                     node_types: list[str] | None = None, limit: int = 80, include_documents: bool = True) -> dict:
        depth = max(1, min(int(depth), 2))
        rel_types = [r for r in (relation_types or SEMANTIC_RELATIONS) if r in SEMANTIC_RELATIONS]
        if node_id.startswith("doc-"):
            return self._document_neighborhood(node_id, allowed)
        rows = self.client.read(
            f"""MATCH (s:Entity {{id: $id}})
                MATCH p = (s)-[rels*1..{depth}]-(n:Entity)
                WHERE all(r IN rels WHERE type(r) IN $types AND {_VISIBLE_REL})
                  AND ($node_types IS NULL OR n.type IN $node_types)
                WITH p LIMIT $limit
                UNWIND relationships(p) AS r
                WITH DISTINCT r
                RETURN startNode(r).id AS source, endNode(r).id AS target, type(r) AS label,
                       coalesce(r.roles, []) AS roles, r.confidence AS confidence,
                       [d IN coalesce(r.source_doc_ids, []) WHERE d IN $allowed] AS docs""",
            id=node_id, types=rel_types, node_types=node_types, allowed=allowed, limit=limit)
        ids = {node_id} | {r["source"] for r in rows} | {r["target"] for r in rows}
        nodes = self.client.read(
            "MATCH (e:Entity) WHERE e.id IN $ids RETURN e.id AS id, e.name AS name, e.type AS type, e.status AS status",
            ids=list(ids))
        edges = [{"id": f"{r['source']}|{r['label']}|{r['target']}", **r} for r in rows]
        if include_documents:
            docs = self.client.read(
                """MATCH (d:Document)-[:DESCRIBES]->(e:Entity {id: $id}) WHERE d.id IN $allowed
                   RETURN d.id AS id, d.title AS name, 'Document' AS type, d.status AS status""",
                id=node_id, allowed=allowed)
            nodes += docs
            edges += [{"id": f"{d['id']}|DESCRIBES|{node_id}", "source": d["id"], "target": node_id,
                       "label": "DESCRIBES", "roles": [], "confidence": 1.0, "docs": [d["id"]]} for d in docs]
        return {"center": node_id, "nodes": nodes, "edges": edges}

    def _document_neighborhood(self, doc_id: str, allowed: list[str]) -> dict:
        if doc_id not in allowed:
            return {"center": doc_id, "nodes": [], "edges": []}
        rows = self.client.read(
            """MATCH (d:Document {id: $id})
               OPTIONAL MATCH (d)-[r:DESCRIBES|AUTHORED_BY|ISSUED_BY]->(e:Entity)
               WITH d, collect({source: d.id, target: e.id, label: type(r), name: e.name, type: e.type}) AS meta
               OPTIONAL MATCH (d)<-[:PART_OF]-(:Chunk)-[:MENTIONS]->(m:Entity) WHERE m.status = 'validated'
               WITH d, meta, collect(DISTINCT {id: m.id, name: m.name, type: m.type})[..25] AS mentioned
               OPTIONAL MATCH (d)-[v:SUPERSEDES|DUPLICATE_OF]-(o:Document) WHERE o.id IN $allowed
               RETURN d {.id, .title, .status} AS doc, meta, mentioned,
                      collect({source: startNode(v).id, target: endNode(v).id, label: type(v), name: o.title,
                               other: o.id}) AS versions""", id=doc_id, allowed=allowed)
        row = rows[0]
        nodes = {doc_id: {"id": doc_id, "name": row["doc"]["title"], "type": "Document", "status": row["doc"]["status"]}}
        edges = []
        for m in row["mentioned"]:
            if m["id"]:
                nodes[m["id"]] = {"id": m["id"], "name": m["name"], "type": m["type"]}
                edges.append({"id": f"{doc_id}|MENTIONS|{m['id']}", "source": doc_id, "target": m["id"],
                              "label": "MENTIONS", "roles": [], "confidence": None, "docs": [doc_id]})
        for m in row["meta"]:
            if m["target"]:
                nodes[m["target"]] = {"id": m["target"], "name": m["name"], "type": m["type"]}
                edges = [e for e in edges if e["target"] != m["target"]]
                edges.append({"id": f"{doc_id}|{m['label']}|{m['target']}", "source": doc_id, "target": m["target"],
                              "label": m["label"], "roles": [], "confidence": None, "docs": [doc_id]})
        for v in row["versions"]:
            if v["other"]:
                nodes[v["other"]] = {"id": v["other"], "name": v["name"], "type": "Document"}
                edges.append({"id": f"{v['source']}|{v['label']}|{v['target']}", "source": v["source"],
                              "target": v["target"], "label": v["label"], "roles": [], "confidence": None, "docs": []})
        return {"center": doc_id, "nodes": list(nodes.values()), "edges": edges}

    def overview(self, allowed: list[str], limit: int = 60, types: list[str] | None = None) -> dict:
        """Vue d'ensemble lisible : entités les plus connectées et relations entre elles."""
        top = self.client.read(
            f"""MATCH (e:Entity)-[r]-(:Entity)
                WHERE type(r) IN $rels AND type(r) <> 'BELONGS_TO' AND {_VISIBLE_REL}
                  AND ($types IS NULL OR e.type IN $types)
                RETURN e.id AS id, e.name AS name, e.type AS type, e.status AS status, count(r) AS degree
                ORDER BY degree DESC, id LIMIT $limit""", rels=SEMANTIC_RELATIONS, types=types, allowed=allowed,
            limit=limit)
        ids = [t["id"] for t in top]
        edges = self.client.read(
            f"""MATCH (a:Entity)-[r]->(b:Entity) WHERE a.id IN $ids AND b.id IN $ids AND type(r) IN $rels
                  AND type(r) <> 'BELONGS_TO' AND {_VISIBLE_REL}
                RETURN a.id + '|' + type(r) + '|' + b.id AS id, a.id AS source, b.id AS target, type(r) AS label,
                       coalesce(r.roles, []) AS roles, r.confidence AS confidence""",
            ids=ids, rels=SEMANTIC_RELATIONS, allowed=allowed)
        return {"center": None, "nodes": top, "edges": edges}

    def documents(self, allowed: list[str], include_hidden: bool = False) -> list[dict]:
        query = """MATCH (d:Document) WHERE d.id IN $allowed OR $hidden
                   OPTIONAL MATCH (d)<-[:PART_OF]-(c:Chunk)
                   RETURN d.id AS id, d.title AS title, d.file_name AS file_name, d.reference AS reference,
                          d.version AS version, toString(d.doc_date) AS date, d.doc_type AS doc_type,
                          d.status AS status, d.classification AS classification, d.diffusion AS diffusion,
                          d.department_name AS department, d.author_name AS author, d.format AS format,
                          d.ocr_used AS ocr_used, d.quality_score AS quality_score, d.issues AS issues,
                          count(c) AS chunks
                   ORDER BY d.title"""
        return self.client.read(query, allowed=allowed, hidden=include_hidden)

    def document(self, doc_id: str, allowed: list[str], include_hidden: bool = False) -> dict | None:
        if doc_id not in allowed and not include_hidden:
            return None
        rows = self.client.read(
            """MATCH (d:Document {id: $id})
               OPTIONAL MATCH (d)<-[:PART_OF]-(c:Chunk)
               WITH d, c ORDER BY c.index
               WITH d, collect(c {.id, .index, .section, .page, .text}) AS chunks
               OPTIONAL MATCH (d)<-[:PART_OF]-(:Chunk)-[:MENTIONS]->(e:Entity)
               WITH d, chunks, collect(DISTINCT e {.id, .name, .type}) AS entities
               OPTIONAL MATCH (d)-[:DESCRIBES]->(x:Entity)
               RETURN d {.*, doc_date: toString(d.doc_date), minhash: null} AS document, chunks, entities,
                      collect(DISTINCT x {.id, .name, .type}) AS describes""", id=doc_id)
        if not rows:
            return None
        row = rows[0]
        return {**row["document"], "chunks": row["chunks"], "entities": row["entities"], "describes": row["describes"]}

    def ingestion_runs(self, limit: int = 20) -> list[dict]:
        return self.client.read(
            "MATCH (r:IngestionRun) RETURN r {.*, details: null} AS run ORDER BY r.started_at DESC LIMIT $limit",
            limit=limit)
