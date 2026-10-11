"""Reconnaissance d'entités dans un texte (*entity linking*).

Deux mécanismes complémentaires :

1. **Dictionnaire (gazetteer)** construit à partir du référentiel : chaque nom et alias est
   recherché dans le texte normalisé (minuscules, sans accents), en privilégiant la mention
   la plus longue (« projet Sentinel » l'emporte sur « Sentinel »). Les sigles courts en
   majuscules (DSI, DG, PPE...) sont recherchés en respectant la casse pour éviter les faux
   positifs. Les alias ambigus sont départagés par le contexte.
2. **NER statistique** (spaCy `fr_core_news_md`, étiquette PER) pour repérer les personnes
   absentes du référentiel. Ces mentions sont résolues de façon approximative ; à défaut,
   elles produisent une entité `candidate` (à valider par un humain).
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from core.models import Mention
from core.text import fold_accents, normalize_key, normalize_with_map
from extraction.referential import Referential
from extraction.resolver import EntityResolver

logger = logging.getLogger(__name__)

_ACRONYM = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,5}$")
_WINDOW = 90  # caractères de contexte pour départager un alias ambigu


class EntityLinker:
    def __init__(self, referential: Referential, use_ner: bool = True) -> None:
        self.ref = referential
        self.resolver = EntityResolver(referential)
        self.use_ner = use_ner
        lower_aliases: dict[str, tuple[str, bool]] = {}
        acronyms: dict[str, str] = {}
        for entity in referential.entities.values():
            for surface in entity.all_surfaces:
                if _ACRONYM.match(surface) and len(surface) <= 6:
                    acronyms[fold_accents(surface)] = entity.id
                else:
                    lower_aliases.setdefault(normalize_key(surface), (entity.id, False))
            for surface in entity.title_aliases:
                lower_aliases.setdefault(normalize_key(surface), (entity.id, True))
        self._alias_map = lower_aliases
        self._acronym_map = acronyms
        self._ambiguous_keys = {normalize_key(a.surface) for a in referential.ambiguous}
        pattern_keys = sorted(set(lower_aliases) | self._ambiguous_keys, key=len, reverse=True)
        self._lower_re = re.compile(r"(?<![\w])(" + "|".join(re.escape(k) for k in pattern_keys) + r")(?![\w])")
        acro_keys = sorted(acronyms, key=len, reverse=True)
        self._acro_re = re.compile(r"(?<![\w-])(" + "|".join(re.escape(k) for k in acro_keys) + r")(?![\w-])")

    # ------------------------------------------------------------------
    def find_mentions(self, text: str) -> list[Mention]:
        mentions: list[Mention] = []
        normalized, mapping = normalize_with_map(text)
        for m in self._lower_re.finditer(normalized):
            start, end = mapping[m.start()], mapping[m.end() - 1] + 1
            key = m.group(1)
            surface = text[start:end]
            if key in self._ambiguous_keys and key not in self._alias_map:
                context = text[max(0, start - _WINDOW): end + _WINDOW]
                chosen = self.resolver.disambiguate(surface, context)
                entity_type = self.ref.entities[chosen].type if chosen else None
                mentions.append(Mention(surface=surface, start=start, end=end, entity_id=chosen,
                                        entity_type=entity_type, method="context",
                                        confidence=0.85 if chosen else 0.0))
                continue
            entity_id, is_title = self._alias_map[key]
            mentions.append(Mention(surface=surface, start=start, end=end, entity_id=entity_id,
                                    entity_type=self.ref.entities[entity_id].type,
                                    method="exact" if normalize_key(self.ref.name(entity_id)) == key else "alias",
                                    title_alias=is_title))
        # Sigles : recherche sensible à la casse sur le texte sans accents (même longueur).
        folded = fold_accents(text)
        if len(folded) == len(text):
            for m in self._acro_re.finditer(folded):
                entity_id = self._acronym_map[m.group(1)]
                mentions.append(Mention(surface=text[m.start():m.end()], start=m.start(), end=m.end(),
                                        entity_id=entity_id, entity_type=self.ref.entities[entity_id].type,
                                        method="alias"))
        mentions = _remove_overlaps(mentions)
        if self.use_ner:
            mentions = self._add_ner_persons(text, mentions)
        return sorted(mentions, key=lambda x: x.start)

    def _add_ner_persons(self, text: str, mentions: list[Mention]) -> list[Mention]:
        nlp = _spacy_model()
        if nlp is None:
            return mentions
        taken = [(m.start, m.end) for m in mentions]
        for ent in nlp(text).ents:
            if ent.label_ != "PER":
                continue
            if any(not (ent.end_char <= s or ent.start_char >= e) for s, e in taken):
                continue
            surface = ent.text.strip()
            tokens = surface.split()
            # Exiger au moins deux mots capitalisés limite les faux positifs du NER.
            if len(tokens) < 2 or not all(t[:1].isupper() for t in tokens):
                continue
            resolution = self.resolver.resolve(surface, type_hint="Person")
            mentions.append(Mention(surface=surface, start=ent.start_char, end=ent.end_char,
                                    entity_id=resolution.entity_id, entity_type="Person", method="ner",
                                    confidence=resolution.score if resolution.entity_id else 0.5))
        return mentions


def _remove_overlaps(mentions: list[Mention]) -> list[Mention]:
    """Conserve la mention la plus longue en cas de chevauchement."""
    kept: list[Mention] = []
    for m in sorted(mentions, key=lambda x: (-(x.end - x.start), x.start)):
        if all(m.end <= k.start or m.start >= k.end for k in kept):
            kept.append(m)
    return kept


@lru_cache(maxsize=1)
def _spacy_model():
    try:
        import spacy

        return spacy.load("fr_core_news_md", exclude=["lemmatizer", "morphologizer", "attribute_ruler"])
    except Exception as exc:  # modèle absent : le NER est simplement désactivé
        logger.warning("Modèle spaCy indisponible, NER désactivé", extra={"error": str(exc)})
        return None
