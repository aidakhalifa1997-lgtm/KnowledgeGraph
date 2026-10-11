"""Résolution d'entités : relier une mention textuelle à une entité canonique.

Cascade (de la plus sûre à la moins sûre), inspirée du pipeline *blocking -> matching* des
travaux sur la résolution d'entités (Christophides et al., 2020) :

1. correspondance exacte sur le nom ou un alias normalisé (casse, accents, ponctuation) ;
2. retrait des civilités (M., Mme, Dr...) puis nouvel essai ;
3. initiale + nom de famille (« K. El Fassi ») avec unicité exigée ;
4. alias ambigus (« Sentinel » : projet ou application ?) départagés par le contexte ;
5. correspondance approximative (rapidfuzz) restreinte au type attendu (« blocage » par type).

Pour l'étape 5, trois zones de décision (Fellegi et Sunter, 1969) :
- score >= SEUIL_HAUT : lien accepté ;
- SEUIL_BAS <= score < SEUIL_HAUT : lien *possible*, non appliqué automatiquement : la mention
  devient une entité `candidate` portant `possible_match` (revue humaine) ;
- score < SEUIL_BAS : aucune correspondance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from core.text import normalize_key
from extraction.referential import Referential

HIGH_THRESHOLD = 90.0
LOW_THRESHOLD = 80.0
_CIVILITY = re.compile(r"^(m\.|mr\.?|mme\.?|mlle\.?|dr\.?|pr\.?|monsieur|madame|mademoiselle)\s+", re.IGNORECASE)


@dataclass
class Resolution:
    entity_id: str | None
    method: str  # exact | civility | initials | context | fuzzy | none | ambiguous
    score: float
    possible_match: str | None = None


class EntityResolver:
    def __init__(self, referential: Referential) -> None:
        self.ref = referential
        self._index: dict[str, set[str]] = {}
        for entity in referential.entities.values():
            for surface in [*entity.all_surfaces, *entity.title_aliases]:
                self._index.setdefault(normalize_key(surface), set()).add(entity.id)
        self._ambiguous = {normalize_key(a.surface): a for a in referential.ambiguous}
        # Choix des surfaces candidates pour l'appariement approximatif, par type.
        self._fuzzy_choices: dict[str, dict[str, str]] = {}
        for entity in referential.entities.values():
            bucket = self._fuzzy_choices.setdefault(entity.type, {})
            for surface in entity.all_surfaces:
                key = normalize_key(surface)
                if len(key) >= 5:
                    bucket[key] = entity.id

    # ------------------------------------------------------------------ helpers
    def _filter(self, ids: set[str], type_hint: str | None) -> set[str]:
        if not type_hint:
            return ids
        return {i for i in ids if self.ref.entities[i].type == type_hint}

    def disambiguate(self, surface: str, context: str) -> str | None:
        """Choisit l'entité d'un alias ambigu à partir des indices présents dans le contexte."""
        alias = self._ambiguous.get(normalize_key(surface))
        if alias is None:
            return None
        context_key = normalize_key(context)
        scores = []
        for entity_id, cues in alias.candidates:
            hits = sum(1 for cue in cues if re.search(rf"\b{re.escape(normalize_key(cue))}\b", context_key))
            scores.append((hits, entity_id))
        scores.sort(reverse=True)
        if scores[0][0] > 0 and (len(scores) == 1 or scores[0][0] > scores[1][0]):
            return scores[0][1]
        return None

    def is_ambiguous_surface(self, surface: str) -> bool:
        return normalize_key(surface) in self._ambiguous

    # ------------------------------------------------------------------ API
    def resolve(self, surface: str, type_hint: str | None = None, context: str = "") -> Resolution:
        key = normalize_key(surface)
        if not key:
            return Resolution(None, "none", 0.0)

        if key in self._ambiguous and (type_hint is None or len(self._filter(
                {c for c, _ in self._ambiguous[key].candidates}, type_hint)) != 1):
            chosen = self.disambiguate(surface, context or surface)
            if chosen:
                return Resolution(chosen, "context", 0.85)
            return Resolution(None, "ambiguous", 0.0)
        if key in self._ambiguous and type_hint:
            only = self._filter({c for c, _ in self._ambiguous[key].candidates}, type_hint)
            return Resolution(next(iter(only)), "context", 0.85)

        ids = self._filter(self._index.get(key, set()), type_hint)
        if len(ids) == 1:
            return Resolution(next(iter(ids)), "exact", 1.0)

        stripped = _CIVILITY.sub("", key).strip()
        if stripped != key:
            ids = self._filter(self._index.get(stripped, set()), type_hint)
            if len(ids) == 1:
                return Resolution(next(iter(ids)), "civility", 0.97)

        if type_hint in (None, "Person"):
            m = re.match(r"^([a-z])\.?\s+([a-z' -]{3,})$", stripped)
            if m:
                initial, last = m.group(1), m.group(2).strip()
                matches = [p.id for p in self.ref.by_type("Person")
                           if normalize_key(p.name).endswith(" " + last) and normalize_key(p.name).startswith(initial)]
                if len(matches) == 1:
                    return Resolution(matches[0], "initials", 0.9)

        if len(stripped) < 5:
            return Resolution(None, "none", 0.0)
        types = [type_hint] if type_hint else list(self._fuzzy_choices)
        best: tuple[float, str] | None = None
        for t in types:
            choices = self._fuzzy_choices.get(t, {})
            if not choices:
                continue
            result = process.extractOne(stripped, list(choices), scorer=fuzz.token_sort_ratio)
            if result and (best is None or result[1] > best[0]):
                best = (float(result[1]), choices[result[0]])
        if best is None:
            return Resolution(None, "none", 0.0)
        score, entity_id = best
        if score >= HIGH_THRESHOLD:
            return Resolution(entity_id, "fuzzy", round(score / 100, 3))
        if score >= LOW_THRESHOLD:
            return Resolution(None, "none", round(score / 100, 3), possible_match=entity_id)
        return Resolution(None, "none", round(score / 100, 3))
