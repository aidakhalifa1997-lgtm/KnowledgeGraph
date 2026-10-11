"""Schéma physique du graphe dans Neo4j : contraintes d'unicité et index.

Modèle (graphe de propriétés) :

    (:Document)<-[:PART_OF]-(:Chunk)-[:NEXT]->(:Chunk)
    (:Chunk)-[:MENTIONS]->(:Entity:<Type>)
    (:Document)-[:DESCRIBES|AUTHORED_BY|ISSUED_BY]->(:Entity)
    (:Document)-[:SUPERSEDES|DUPLICATE_OF|SIMILAR_TO]->(:Document)
    (:Entity)-[:WORKS_IN|PART_OF|HAS_EXPERTISE|PARTICIPATES_IN|RESPONSIBLE_FOR|OWNS|
               DELIVERS|IMPACTS|DEPENDS_ON|USES|REFERENCES|COVERS|BELONGS_TO]->(:Entity)
    (:IngestionRun)

Chaque entité porte deux étiquettes : `Entity` (étiquette commune, porteuse de la contrainte
d'unicité de l'identifiant) et son type (`Person`, `Project`...).

Index :
- vectoriel (HNSW, cosinus) sur `Chunk.embedding` pour la recherche sémantique ;
- plein texte (Lucene, analyseur français) sur `Chunk.search_text` pour la recherche lexicale
  BM25 ;
- plein texte (analyseur avec repli des accents) sur le nom des entités ;
- index classiques sur les propriétés filtrées fréquemment.
"""

from __future__ import annotations

ENTITY_LABELS = ["Person", "Department", "Project", "Procedure", "System", "Concept", "Domain"]
SEMANTIC_RELATIONS = ["WORKS_IN", "PART_OF", "HAS_EXPERTISE", "PARTICIPATES_IN", "RESPONSIBLE_FOR", "OWNS",
                      "DELIVERS", "IMPACTS", "DEPENDS_ON", "USES", "REFERENCES", "COVERS", "BELONGS_TO"]

VECTOR_INDEX = "chunk_embedding_vec"
CHUNK_FULLTEXT = "chunk_text_ft"
ENTITY_FULLTEXT = "entity_name_ft"


def schema_statements(embedding_dim: int) -> list[str]:
    return [
        "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
        "CREATE CONSTRAINT run_id IF NOT EXISTS FOR (r:IngestionRun) REQUIRE r.id IS UNIQUE",
        "CREATE INDEX document_hash IF NOT EXISTS FOR (d:Document) ON (d.content_hash)",
        "CREATE INDEX document_reference IF NOT EXISTS FOR (d:Document) ON (d.reference)",
        "CREATE INDEX document_status IF NOT EXISTS FOR (d:Document) ON (d.status)",
        "CREATE INDEX chunk_doc IF NOT EXISTS FOR (c:Chunk) ON (c.doc_id)",
        "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
        "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
        (f"CREATE VECTOR INDEX {VECTOR_INDEX} IF NOT EXISTS FOR (c:Chunk) ON c.embedding "
         f"OPTIONS {{indexConfig: {{`vector.dimensions`: {int(embedding_dim)}, `vector.similarity_function`: 'cosine'}}}}"),
        (f"CREATE FULLTEXT INDEX {CHUNK_FULLTEXT} IF NOT EXISTS FOR (c:Chunk) ON EACH [c.search_text] "
         "OPTIONS {indexConfig: {`fulltext.analyzer`: 'french'}}"),
        (f"CREATE FULLTEXT INDEX {ENTITY_FULLTEXT} IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.aliases_text] "
         "OPTIONS {indexConfig: {`fulltext.analyzer`: 'standard-folding'}}"),
    ]
