"""Fusion des relations issues de plusieurs extracteurs (règles et LLM).

Clé de fusion : (sujet, relation, objet). Lorsque deux extracteurs indépendants proposent la
même relation, la confiance est renforcée (accord = indice de fiabilité) ; les preuves et
les rôles sont conservés.
"""

from __future__ import annotations

from core.models import ExtractedRelation

AGREEMENT_BONUS = 0.1


def merge_relations(relations: list[ExtractedRelation]) -> list[ExtractedRelation]:
    merged: dict[tuple[str, str, str, str], ExtractedRelation] = {}
    extractors: dict[tuple[str, str, str, str], set[str]] = {}
    for rel in relations:
        key = (rel.subject_id, rel.relation, rel.object_id, rel.chunk_id)
        if key not in merged:
            merged[key] = rel.model_copy(deep=True)
            extractors[key] = {rel.extractor}
            continue
        current = merged[key]
        current.roles = sorted(set(current.roles) | set(rel.roles))
        if rel.extractor not in extractors[key]:
            extractors[key].add(rel.extractor)
            current.confidence = min(1.0, max(current.confidence, rel.confidence) + AGREEMENT_BONUS)
        else:
            current.confidence = max(current.confidence, rel.confidence)
    for key, rel in merged.items():
        if len(extractors[key]) > 1:
            rel.extractor = "rules+llm"
    return list(merged.values())


def extractor_sets(relations: list[ExtractedRelation]) -> dict[tuple[str, str, str], set[str]]:
    sets: dict[tuple[str, str, str], set[str]] = {}
    for rel in relations:
        sets.setdefault((rel.subject_id, rel.relation, rel.object_id), set()).add(rel.extractor)
    return sets
