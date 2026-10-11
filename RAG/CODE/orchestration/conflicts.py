"""Détection des informations contradictoires dans le contexte récupéré.

Deux mécanismes déterministes :

1. **Versions** : plusieurs versions d'un même document (même référence) dans le contexte ;
   la version la plus récente fait foi, l'ancienne est signalée comme remplacée.
2. **Valeurs divergentes** : dans les phrases du contexte qui partagent le sujet de la question,
   une même grandeur (%, mois, jours, heures, minutes) prend des valeurs différentes selon les
   documents (ex. revue périodique à 12 mois dans la procédure v2, 24 mois dans le guide
   utilisateur). La valeur retenue est celle du document normatif (procédure) le plus récent
   et en vigueur ; les autres sont signalées avec leur source.

Ces règles ne détectent pas toutes les contradictions (formulations sans valeur numérique,
contradictions logiques) : c'est une limite assumée, que l'usage d'un LLM peut compléter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.text import content_terms, split_sentences
from orchestration.sufficiency import term_key

_QUANTITY = re.compile(r"(\d+(?:[.,]\d+)?)\s*(%|pour ?cent|mois|jours?(?: ouvrés| ouvres)?|heures?(?: ouvrées)?|minutes?|ans)(?!\w)",
                       re.IGNORECASE)
_UNIT_NORMALIZATION = {"pour cent": "%", "pourcent": "%", "jour": "jours", "heure": "heures", "minute": "minutes"}
_NORMATIVE = {"procedure": 3, "note_de_service": 2, "note_organisation": 2, "charte_projet": 1}


@dataclass
class ValueClaim:
    value: str
    unit: str
    chunk_id: str
    doc_id: str
    title: str
    status: str
    doc_type: str
    doc_date: str | None
    sentence: str


@dataclass
class Conflict:
    kind: str  # version | value
    message: str
    preferred: ValueClaim | None = None
    others: list[ValueClaim] = field(default_factory=list)
    doc_ids: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)


def _unit(raw: str) -> str:
    unit = re.sub(r"\s*ouvr\w+", "", raw.lower()).strip()
    unit = _UNIT_NORMALIZATION.get(unit, unit)
    return unit + "s" if unit in ("jour", "heure", "minute") else unit


def _authority(claim: ValueClaim) -> tuple:
    return (claim.status == "active", _NORMATIVE.get(claim.doc_type, 0), claim.doc_date or "")


def detect_conflicts(question: str, chunks: list) -> list[Conflict]:
    conflicts: list[Conflict] = []
    # 1. Versions multiples d'une même référence.
    by_reference: dict[str, list] = {}
    for chunk in chunks:
        if chunk.reference:
            by_reference.setdefault(chunk.reference, []).append(chunk)
    for reference, items in by_reference.items():
        versions = {(c.version, c.status, c.doc_id, c.doc_date) for c in items}
        if len({v[0] for v in versions}) > 1:
            current = [v for v in versions if v[1] == "active"]
            old = [v for v in versions if v[1] == "superseded"]
            if current and old:
                conflicts.append(Conflict(
                    kind="version", doc_ids=[v[2] for v in versions], chunk_ids=[c.id for c in items],
                    message=(f"Plusieurs versions de {reference} sont présentes : la version {current[0][0]} "
                             f"({current[0][3]}) remplace la version {old[0][0]} ({old[0][3]}) ; "
                             "les informations de l'ancienne version peuvent être obsolètes.")))

    # 2. Valeurs divergentes pour une même grandeur. Pour chaque document et chaque unité, on
    #    retient l'affirmation la plus « dense » (part des termes de la phrase qui relèvent de
    #    la question) : une ligne normative « risque élevé : 12 mois » l'emporte sur une phrase
    #    narrative qui rappelle aussi l'ancienne valeur.
    focus = {term_key(t) for t in content_terms(question)}
    best: dict[tuple[str, str], tuple[float, ValueClaim]] = {}
    for chunk in chunks:
        for sentence in split_sentences(chunk.text):
            sent_terms = {term_key(t) for t in content_terms(sentence)}
            overlap = focus & sent_terms
            if len(overlap) < 2 or len(overlap) < 0.4 * len(focus):
                continue
            density = len(overlap) / max(len(sent_terms), 1)
            m = _QUANTITY.search(sentence)
            if not m:
                continue
            unit = _unit(m.group(2))
            claim = ValueClaim(value=m.group(1).replace(",", "."), unit=unit, chunk_id=chunk.id, doc_id=chunk.doc_id,
                               title=chunk.title, status=chunk.status, doc_type=chunk.doc_type,
                               doc_date=chunk.doc_date, sentence=sentence)
            key = (chunk.doc_id, unit)
            if key not in best or density > best[key][0]:
                best[key] = (density, claim)
    claims: dict[str, list[ValueClaim]] = {}
    for (_, unit), (_, claim) in best.items():
        claims.setdefault(unit, []).append(claim)
    for unit, items in claims.items():
        if len({c.doc_id for c in items}) < 2 or len({c.value for c in items}) < 2:
            continue
        preferred = max(items, key=_authority)
        others = [c for c in items if c.value != preferred.value]
        seen, unique_others = set(), []
        for c in others:
            if (c.value, c.doc_id) not in seen:
                seen.add((c.value, c.doc_id))
                unique_others.append(c)
        details = "; ".join(f"{c.value} {unit} dans « {c.title} »" for c in unique_others[:4])
        conflicts.append(Conflict(
            kind="value", preferred=preferred, others=unique_others, doc_ids=sorted({c.doc_id for c in items}),
            chunk_ids=list(dict.fromkeys([preferred.chunk_id] + [c.chunk_id for c in unique_others])),
            message=(f"Valeurs divergentes ({unit}) : la source de référence « {preferred.title} » indique "
                     f"{preferred.value} {unit}, mais d'autres sources indiquent {details}.")))
    return conflicts
