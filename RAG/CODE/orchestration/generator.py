"""Génération de la réponse.

- `LLMGenerator` : génération par le LLM configuré, contrainte par le prompt système.
- `ExtractiveGenerator` : générateur **hors-ligne** sans LLM. Il sélectionne les phrases du
  contexte les plus pertinentes et les faits du graphe mobilisés, puis les assemble avec leurs
  citations. Il ne peut pas halluciner (il ne reformule rien), mais il ne synthétise pas
  non plus : c'est une baseline extractive, présentée comme telle, qui permet de faire
  fonctionner et d'évaluer la plateforme sans clé d'API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.llm import LLMClient, LLMError
from core.text import content_terms, fold_accents, light_stem, normalize_key, split_sentences
from orchestration.conflicts import Conflict
from orchestration.prompts import SYSTEM_PROMPT, build_user_prompt
from orchestration.sufficiency import QUESTION_FILLERS, TermStatistics, term_key

ABSTAIN_TEXT = "Je ne dispose pas d'informations suffisantes dans les documents accessibles pour répondre à cette question."
_NUMERIC_Q = re.compile(r"\b(combien|quel(le)?s? (est|sont) (le|la|les) (delai|seuil|taux|frequence|plafond|score|"
                        r"indicateur|pourcentage|rto|rpo)|dans quel delai|sous quel delai|en dessous de quel|"
                        r"quel (delai|seuil|taux|pourcentage|indicateur|score))")
_WHO_Q = re.compile(r"^(qui|vers qui|a qui)\b|\bqui (est|sont|pilote|fait|preside|peut)\b")
_SYSTEM_Q = re.compile(r"\b(applications?|outils?|systemes?|plateformes?)\b")
_NUMBER = re.compile(r"\d")


@dataclass
class GenerationInput:
    question: str
    question_type: str
    chunks: list
    facts: list
    conflicts: list[Conflict]
    ambiguous: list[dict]
    seed_names: list[str]
    intent_relations: list[str]
    paths: list[list[str]]
    person_names: list[str]
    system_names: list[str]
    experts: list[dict] | None = None
    seed_ids: list[str] | None = None


@dataclass
class GenerationOutput:
    text: str
    generator: str
    llm_model: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None


_VERSION_Q = re.compile(r"\b(vigueur|version|a jour|actuel\w*|derniere|remplac\w*|obsolete)\b")


def text_units(text: str) -> list[str]:
    """Découpe un passage en unités de sens : une phrase, ou une phrase d'introduction
    (« ... comme suit : ») suivie de ses puces, qui n'ont de sens qu'ensemble."""
    units: list[str] = []
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    header: list[str] | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|"):
            # Tableau : chaque ligne est rattachée aux intitulés de colonnes.
            cells = [c.strip() for c in line.strip("|").split("|")]
            if header is None:
                header = cells
            else:
                pairs = [f"{h} : {c}" for h, c in zip(header[1:], cells[1:], strict=False)]
                units.append(f"{cells[0]} — " + " ; ".join(pairs) + ".")
            i += 1
            continue
        header = None
        if line.endswith(":") and i + 1 < len(lines) and lines[i + 1].startswith(("-", "•")):
            items = []
            j = i + 1
            while j < len(lines) and lines[j].startswith(("-", "•")) and len(" ".join(items)) < 400:
                items.append(lines[j].lstrip("-• ").rstrip(" ;."))
                j += 1
            units.append(f"{line} {' ; '.join(items)}.")
            i = j
            continue
        units += split_sentences(line)
        i += 1
    return units


def alerts_for(inp: GenerationInput) -> list[str]:
    alerts = [c.message for c in inp.conflicts]
    for amb in inp.ambiguous:
        options = " ; ".join(f"{o['name']} ({o['type']})" for o in amb["candidates"])
        alerts.append(f"« {amb['surface']} » est ambigu et peut désigner : {options}.")
    return alerts


class LLMGenerator:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def generate(self, inp: GenerationInput) -> GenerationOutput:
        prompt = build_user_prompt(inp.question, inp.chunks, inp.facts, alerts_for(inp))
        result = self.llm.complete(SYSTEM_PROMPT, prompt)
        return GenerationOutput(text=result.text, generator=f"llm:{result.provider}", llm_model=result.model,
                                latency_ms=result.latency_ms, input_tokens=result.input_tokens,
                                output_tokens=result.output_tokens)


class ExtractiveGenerator:
    def __init__(self, stats: TermStatistics) -> None:
        self.stats = stats

    def _score_units(self, inp: GenerationInput) -> list[tuple[float, str, int]]:
        q_norm = normalize_key(inp.question)
        q_terms = [t for t in dict.fromkeys(content_terms(inp.question)) if fold_accents(t) not in QUESTION_FILLERS]
        weights = {light_stem(t): self.stats.idf(term_key(t)) for t in q_terms}
        total = sum(weights.values()) or 1.0
        seeds = [normalize_key(n) for n in inp.seed_names if n]
        persons = [normalize_key(n) for n in inp.person_names]
        systems = [normalize_key(n) for n in inp.system_names]
        numeric_q, who_q, system_q = bool(_NUMERIC_Q.search(q_norm)), bool(_WHO_Q.search(q_norm)), bool(_SYSTEM_Q.search(q_norm))
        scored: list[tuple[float, str, int]] = []
        for rank, chunk in enumerate(inp.chunks):
            for unit in text_units(chunk.text):
                if len(unit) < 25 or unit.endswith(":"):
                    continue
                u_norm = normalize_key(unit)
                stems = {light_stem(t) for t in content_terms(unit)}
                score = sum(w for st, w in weights.items() if st in stems) / total
                if any(seed in u_norm for seed in seeds):
                    score += 0.3
                if numeric_q and _NUMBER.search(unit):
                    score += 0.25
                if who_q and any(p in u_norm for p in persons):
                    score += 0.25
                if system_q and any(sy in u_norm for sy in systems):
                    score += 0.2
                score += 0.15 / (1 + rank)
                if chunk.status == "superseded":
                    score *= 0.85
                scored.append((score, unit, rank))
        scored.sort(key=lambda x: -x[0])
        return scored

    def _relevant_facts(self, inp: GenerationInput) -> list:
        intent = set(inp.intent_relations)
        seeds = set(inp.seed_ids or [])

        def priority(fact) -> int:
            touches = fact.subject_id in seeds or fact.object_id in seeds
            return 0 if touches and fact.relation in intent else 1 if touches else 2 if fact.relation in intent else 3

        ranked = sorted(inp.facts, key=lambda f: (priority(f), -f.score))
        return [f for f in ranked if priority(f) < 3][:8] or ranked[:5]

    def generate(self, inp: GenerationInput) -> GenerationOutput:
        chunk_index = {c.id: i + 1 for i, c in enumerate(inp.chunks)}

        def cite(chunk_ids: list[str]) -> str:
            refs = sorted({chunk_index[c] for c in chunk_ids if c in chunk_index})
            return " ".join(f"[C{r}]" for r in refs[:3])

        sections: dict[str, str] = {}
        # 1. Valeur de référence en cas de valeurs divergentes.
        preferred = next((c.preferred for c in inp.conflicts if c.kind == "value" and c.preferred), None)
        used_units: set[str] = set()
        if preferred is not None and preferred.chunk_id in chunk_index:
            chunk = inp.chunks[chunk_index[preferred.chunk_id] - 1]
            unit = next((u for u in text_units(chunk.text) if preferred.sentence in u or u in preferred.sentence),
                        preferred.sentence)
            used_units.add(unit)
            sections["reference"] = (f"Selon la source de référence en vigueur (« {chunk.title} ») : "
                                     f"{unit} {cite([preferred.chunk_id])}")
        # 2. Question portant sur la version en vigueur : réponse tirée des métadonnées.
        if _VERSION_Q.search(normalize_key(inp.question)):
            current = [c for c in inp.chunks if c.status == "active" and c.reference
                       and any(normalize_key(c.reference) in normalize_key(n) or normalize_key(n) in normalize_key(c.title)
                               for n in inp.seed_names if n)]
            if current:
                c = current[0]
                sections["version"] = (f"Le document « {c.title} » ({c.reference}) est en vigueur dans sa version "
                                       f"{c.version} du {c.doc_date}. {cite([c.id])}")
        # 3. Ambiguïté.
        if inp.ambiguous:
            texts = []
            for amb in inp.ambiguous:
                options = " ; ".join(f"{o['name']} ({o['type']})" for o in amb["candidates"])
                texts.append(f"Remarque : la question est ambiguë, « {amb['surface']} » peut désigner {options}. "
                             "Les éléments ci-dessous couvrent ces interprétations.")
            sections["ambiguity"] = " ".join(texts)
        # 4. Experts.
        if inp.experts:
            lines = [f"- {e['name']} (score {e['score']:.2f}, confiance {e['confidence']}) : {e['justification']}"
                     for e in inp.experts[:3]]
            sections["experts"] = "Personnes identifiées à partir des preuves documentaires :\n" + "\n".join(lines)
        # 5. Extraits.
        scored = self._score_units(inp)
        selected: list[tuple[str, int]] = []
        per_doc: dict[str, int] = {}
        best = scored[0][0] if scored else 0.0
        for score, unit, rank in scored:
            if len(selected) >= 3 or score < 0.35 * best:
                break
            doc = inp.chunks[rank].doc_id
            if per_doc.get(doc, 0) >= 2 or unit in used_units or any(unit == u for u, _ in selected):
                continue
            per_doc[doc] = per_doc.get(doc, 0) + 1
            selected.append((unit, rank))
        if selected:
            sections["extracts"] = "Extraits des documents : " + " ".join(f"{u} [C{r + 1}]" for u, r in selected)
        # 6. Faits et chemins du graphe.
        if inp.facts and inp.question_type in ("relational", "multi_hop", "expert", "ambiguous"):
            lines = [f"- {f.text} [{f.id}]{' ' + cite(f.evidence_chunk_ids) if cite(f.evidence_chunk_ids) else ''}"
                     for f in self._relevant_facts(inp)]
            if lines:
                sections["facts"] = "Relations mobilisées dans le graphe de connaissances :\n" + "\n".join(lines)
            if inp.question_type == "multi_hop" and inp.paths:
                fact_map = {f.id: f for f in inp.facts}
                chains = [" → ".join(f"{fact_map[p].text} [{p}]" for p in path)
                          for path in inp.paths if len(path) >= 2 and all(p in fact_map for p in path)]
                if chains:
                    sections["paths"] = ("Raisonnement en plusieurs étapes (chemins parcourus dans le graphe) :\n" +
                                         "\n".join(f"- {c}" for c in chains[:3]))
        # 7. Points d'attention (cités).
        if inp.conflicts:
            sections["conflicts"] = "Points d'attention :\n" + "\n".join(
                f"- {c.message} {cite(c.chunk_ids)}".rstrip() for c in inp.conflicts)

        order = {
            "multi_hop": ["ambiguity", "paths", "facts", "reference", "version", "extracts", "conflicts"],
            "relational": ["ambiguity", "facts", "reference", "version", "extracts", "conflicts"],
            "expert": ["experts", "extracts", "facts", "conflicts"],
            "ambiguous": ["ambiguity", "facts", "extracts", "reference", "version", "conflicts"],
        }.get(inp.question_type, ["ambiguity", "reference", "version", "extracts", "facts", "conflicts"])
        if "version" in sections:  # question sur la version en vigueur : la réponse vient en premier
            order = ["version"] + [k for k in order if k != "version"]
        parts = [sections[k] for k in order if k in sections]
        if not parts:
            return GenerationOutput(text=ABSTAIN_TEXT, generator="extractive")
        parts.append("Note : réponse générée sans LLM (mode extractif) ; les extraits sont repris tels quels des "
                     "documents cités.")
        return GenerationOutput(text="\n\n".join(parts), generator="extractive")


def generate_with_fallback(inp: GenerationInput, llm_generator: LLMGenerator | None,
                           extractive: ExtractiveGenerator) -> GenerationOutput:
    if llm_generator is not None:
        try:
            return llm_generator.generate(inp)
        except LLMError as exc:
            output = extractive.generate(inp)
            output.error = f"LLM indisponible ({exc}) : bascule sur le générateur extractif"
            return output
    return extractive.generate(inp)
