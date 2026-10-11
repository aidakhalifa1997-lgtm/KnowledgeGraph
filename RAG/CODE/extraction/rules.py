"""Extracteur de relations par règles (déterministe, hors-ligne).

Fonctionnement pour chaque passage :
1. découpage en phrases ;
2. pour chaque règle et chaque déclencheur trouvé dans la phrase, choix des arguments :
   mention de type sujet et mention de type objet les plus proches du déclencheur, du bon
   côté, à distance raisonnable (ou toutes les mentions d'une énumération si `multi`) ;
3. à défaut d'argument explicite : argument « implicite » (l'entité décrite par le
   document, ex. la procédure dans « la présente procédure »), phrases précédentes
   (`lookback`) ou résolution simple d'un pronom en début de phrase (« Elle est... ») ;
4. règles spécifiques codées : titre de fonction (« Directrice Conformité, Mme X »),
   rattachement entre parenthèses (« X (DSI) ») et juxtaposition « Pôle X de la DSI ».

Chaque relation conserve la phrase source comme preuve (provenance).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from core.models import ExtractedRelation, Mention
from core.ontology import validate_relation
from core.text import normalize_key, normalize_with_map, split_sentences
from extraction.referential import Referential

_PRONOUN_START = re.compile(r"^(Il|Elle|Ils|Elles|Son|Sa|Ses|Celle-ci|Celui-ci)\b")
_SUBUNIT_PREFIX = ("pôle", "pole", "cellule", "service", "bureau")


@dataclass
class Rule:
    name: str
    relation: str
    subject_types: set[str]
    object_types: set[str]
    triggers: list[re.Pattern]
    roles: list[str] = field(default_factory=list)
    subject_side: str = "any"
    object_side: str = "any"
    multi: str = "none"
    implicit: str = "none"
    lookback: int = 0
    max_distance: int = 80
    confidence: float = 0.8
    explicit_subject: bool = True  # False : le sujet vient uniquement du contexte du document
    cross_semicolon: bool = False  # True : une énumération peut franchir un « ; »
    suppressed_by: list[str] = field(default_factory=list)  # relations prioritaires dans la phrase


@dataclass
class DocContext:
    doc_id: str
    described_ids: list[str]
    described_types: dict[str, str]


@dataclass
class _Cand:
    mention: Mention
    start: int
    end: int
    virtual: bool = False  # mention issue d'une phrase précédente (lookback / pronom)
    rank: int = 0  # ordre d'apparition dans la phrase précédente (pronoms)


def load_rules(path: str | Path) -> list[Rule]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    rules = []
    for item in data["rules"]:
        rules.append(Rule(
            name=item["name"], relation=item["relation"],
            subject_types=set(item["subject_types"]), object_types=set(item["object_types"]),
            triggers=[re.compile(t) for t in item["triggers"]], roles=list(item.get("roles", [])),
            subject_side=item.get("subject_side", "any"), object_side=item.get("object_side", "any"),
            multi=item.get("multi", "none"), implicit=item.get("implicit", "none"),
            lookback=int(item.get("lookback", 0)), max_distance=int(item.get("max_distance", 80)),
            confidence=float(item.get("confidence", 0.8)),
            explicit_subject=bool(item.get("explicit_subject", True)),
            cross_semicolon=bool(item.get("cross_semicolon", False)),
            suppressed_by=list(item.get("suppressed_by", [])),
        ))
    return rules


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    spans, cursor = [], 0
    for sent in split_sentences(text):
        idx = text.find(sent, cursor)
        if idx < 0:
            idx = text.find(sent)
        if idx < 0:
            continue
        spans.append((idx, idx + len(sent), sent))
        cursor = idx + len(sent)
    return spans


def _distance(c: _Cand, t_start: int, t_end: int) -> float:
    if c.virtual:
        return 50.0
    if c.end <= t_start:
        return (t_start - c.end) * 0.6  # léger avantage aux arguments placés avant le déclencheur
    if c.start >= t_end:
        return float(c.start - t_end)
    return 0.0


def _side_ok(c: _Cand, side: str, t_start: int, t_end: int) -> bool:
    # Une mention peut chevaucher la fin (ou le début) du déclencheur lorsque son alias
    # commence par un article (« la DSI ») : elle reste du bon côté si elle le dépasse.
    if side == "left":
        return c.start < t_start and c.end <= t_end
    if side == "right":
        return c.end > t_end and c.start >= t_start and not c.virtual
    return True


class RuleExtractor:
    def __init__(self, referential: Referential, rules_path: str | Path) -> None:
        self.ref = referential
        self.rules = load_rules(rules_path)

    def _type(self, entity_id: str) -> str:
        return self.ref.entities[entity_id].type if entity_id in self.ref.entities else entity_id.split(":")[0]

    def extract(self, chunk_id: str, text: str, mentions: list[Mention], ctx: DocContext) -> list[ExtractedRelation]:
        linked = [m for m in mentions if m.entity_id]
        spans = _sentence_spans(text)
        found: dict[tuple[str, str, str], ExtractedRelation] = {}

        def add(subject_id: str, relation: str, object_id: str, roles: list[str], evidence: str, conf: float) -> bool:
            if subject_id == object_id:
                return False
            ok, _ = validate_relation(self._type(subject_id), relation, self._type(object_id))
            if not ok:
                return False
            key = (subject_id, relation, object_id)
            if key in found:
                merged = sorted(set(found[key].roles) | set(roles))
                found[key].roles = merged
                found[key].confidence = max(found[key].confidence, conf)
                return True
            found[key] = ExtractedRelation(subject_id=subject_id, relation=relation, object_id=object_id,
                                           roles=list(roles), evidence=evidence.strip()[:600], chunk_id=chunk_id,
                                           doc_id=ctx.doc_id, confidence=round(conf, 3), extractor="rules")
            return True

        for s_idx, (s_start, s_end, sentence) in enumerate(spans):
            in_sentence = [_Cand(m, m.start, m.end) for m in linked if s_start <= m.start and m.end <= s_end]
            previous: list[_Cand] = []  # phrases précédentes, de la plus proche à la plus lointaine
            for back in range(1, 3):
                if s_idx - back < 0:
                    break
                p_start, p_end, _ = spans[s_idx - back]
                previous.extend(_Cand(m, s_start, s_start, virtual=True) for m in linked
                                if p_start <= m.start and m.end <= p_end)
            if s_idx >= 1:
                p_start, p_end, _ = spans[s_idx - 1]
                previous_sentence = [_Cand(m, s_start, s_start, virtual=True) for m in linked
                                     if p_start <= m.start and m.end <= p_end]
            else:
                previous_sentence = []
            for rank, cand in enumerate(previous_sentence):
                cand.rank = rank
            pronoun = bool(_PRONOUN_START.match(sentence))
            produced: list[tuple[str, str, str]] = []
            normalized, mapping = normalize_with_map(sentence)

            for rule in self.rules:
                used_as_object: set[str] = set()
                for pattern in rule.triggers:
                    for tm in pattern.finditer(normalized):
                        t_start = s_start + mapping[tm.start()]
                        t_end = s_start + mapping[max(tm.end() - 1, tm.start())] + 1
                        pool = list(in_sentence)
                        if rule.lookback:
                            pool += previous[: 10 * rule.lookback]
                        elif pronoun:
                            # Pronom en début de phrase (« Elle », « Son ») : il renvoie le plus
                            # souvent au sujet de la phrase précédente, c.-à-d. sa première mention.
                            pool += previous_sentence
                        noun = tm.groupdict().get("noun") if pattern.groupindex else None
                        subjects = [] if not rule.explicit_subject else self._pick(
                            pool, rule.subject_types, rule.subject_side, rule, t_start, t_end, text,
                            multi=rule.multi in ("subjects", "both"), exclude=used_as_object, allow_title=False)
                        objects = self._pick(pool, rule.object_types, rule.object_side, rule, t_start, t_end, text,
                                             multi=rule.multi in ("objects", "both"), exclude=set(),
                                             allow_title=rule.relation == "WORKS_IN", noun=noun)
                        conf = rule.confidence
                        if not subjects and rule.implicit in ("subject", "both"):
                            subjects = [i for i in ctx.described_ids if ctx.described_types.get(i) in rule.subject_types]
                            conf *= 0.9
                        if not objects and rule.implicit in ("object", "both"):
                            objects = [i for i in ctx.described_ids if ctx.described_types.get(i) in rule.object_types]
                            conf *= 0.9
                        if rule.suppressed_by:
                            blocked = {e for (a, r, b) in produced if r in rule.suppressed_by for e in (a, b)}
                            objects = [o for o in objects if o not in blocked]
                        for s in subjects:
                            for o in objects:
                                if add(s, rule.relation, o, rule.roles, sentence, conf):
                                    produced.append((s, rule.relation, o))
                                    used_as_object.add(o)

            self._title_and_parenthesis_rules(in_sentence, text, sentence, add)
        return list(found.values())

    def _pick(self, pool: list[_Cand], types: set[str], side: str, rule: Rule, t_start: int, t_end: int, text: str,
              *, multi: bool, exclude: set[str], allow_title: bool, noun: str | None = None) -> list[str]:
        def separated(c: _Cand) -> bool:
            if c.virtual or rule.cross_semicolon:
                return False
            lo, hi = (c.end, t_start) if c.end <= t_start else (t_end, c.start)
            return ";" in text[lo:hi]

        cands = [c for c in pool
                 if c.mention.entity_type in types and c.mention.entity_id not in exclude
                 and (allow_title or not c.mention.title_alias)
                 and _side_ok(c, side, t_start, t_end)
                 and _distance(c, t_start, t_end) <= rule.max_distance
                 and not separated(c)]
        # Les mentions des phrases précédentes (pronom, lookback) ne servent qu'en l'absence
        # d'argument explicite dans la phrase elle-même.
        explicit = [c for c in cands if not c.virtual]
        cands = explicit or cands
        if noun:
            # « responsable de ce pôle » : on privilégie l'entité dont le nom commence par « pôle ».
            same_noun = [c for c in cands if normalize_key(c.mention.surface).startswith(noun)]
            cands = same_noun or cands
        if not cands:
            return []
        if multi:
            ordered: list[str] = []
            right = sorted((c for c in cands if c.start >= t_end and not c.virtual), key=lambda c: c.start)
            left = [c for c in cands if c not in right]
            # Une énumération d'objets à droite s'arrête à la première mention d'un autre argument
            # (ex. une autre personne) : « X, spécialiste du ML, et M. Y (DevOps) ».
            stop = min((c.start for c in pool if c.start >= t_end and not c.virtual
                        and c.mention.entity_type not in types and c.mention.entity_type in rule.subject_types),
                       default=None)
            if stop is not None and not set(types) & rule.subject_types:
                right = [c for c in right if c.start < stop]
            for c in sorted(left, key=lambda c: c.start) + right:
                if c.mention.entity_id not in ordered:
                    ordered.append(c.mention.entity_id)
            return ordered
        best = min(cands, key=lambda c: (_distance(c, t_start, t_end), getattr(c, "rank", 0)))
        return [best.mention.entity_id]

    def _title_and_parenthesis_rules(self, cands: list[_Cand], text: str, sentence: str, add) -> None:
        persons = [c for c in cands if c.mention.entity_type == "Person"]
        departments = [c for c in cands if c.mention.entity_type == "Department"]
        # 1. Titre de fonction : « Directrice Conformité, Mme Salma Idrissi » ou l'inverse.
        for d in (c for c in departments if c.mention.title_alias):
            near = [p for p in persons if min(abs(p.start - d.end), abs(d.start - p.end)) <= 45]
            if near:
                best = min(near, key=lambda p: min(abs(p.start - d.end), abs(d.start - p.end)))
                between = text[min(best.end, d.end):max(best.start, d.start)]
                if not any(q is not best and min(best.end, d.end) <= q.start < max(best.start, d.start)
                           for q in persons) and ";" not in between:
                    add(best.mention.entity_id, "WORKS_IN", d.mention.entity_id, [], sentence, 0.8)
        # 2. Rattachement entre parenthèses : « Driss Benjelloun (DSI) », « A et B (DOT) ».
        for d in departments:
            before = text[:d.start].rstrip()
            after = text[d.end:].lstrip()
            if not (before.endswith("(") and after.startswith(")")):
                continue
            paren_pos = len(before) - 1
            chain = sorted((p for p in persons if p.end <= paren_pos), key=lambda p: p.end, reverse=True)
            for i, p in enumerate(chain):
                gap = text[p.end:paren_pos] if i == 0 else text[p.end:chain[i - 1].start]
                gap = re.sub(r"\b(M\.|Mme|Mlle|Dr)\s*", "", gap).strip()
                if (i == 0 and gap == "") or (i > 0 and gap in {"et", ","}):
                    add(p.mention.entity_id, "WORKS_IN", d.mention.entity_id, [], sentence, 0.8)
                else:
                    break
        # 3. Juxtaposition « Pôle X de la DSI » : la sous-entité fait partie de l'entité suivante.
        for a, b in zip(departments, departments[1:], strict=False):
            gap = text[a.end:b.start].strip().lower()
            if gap in {"de la", "du", "de l'", "des", "de"} and a.mention.surface.lower().startswith(_SUBUNIT_PREFIX) \
                    and not a.mention.title_alias and not b.mention.title_alias:
                add(a.mention.entity_id, "PART_OF", b.mention.entity_id, [], sentence, 0.8)
