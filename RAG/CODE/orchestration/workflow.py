"""Workflow de questions-réponses orchestré par LangGraph.

    START → analyze → retrieve → assess ─┬─(suffisant)──────────→ generate → verify → END
                         ↑                ├─(insuffisant, 1er essai)→ expand ─┘ (retour à retrieve)
                         └────────────────┘
                                          └─(insuffisant, après relance)→ abstain → END

Pourquoi LangGraph plutôt qu'une suite d'appels de fonctions :
- l'**état** (question, droits, passages, faits, diagnostics) est un objet typé partagé, inspectable
  à chaque étape et sérialisable pour l'audit ;
- les **transitions conditionnelles** (suffisance du contexte) et la **boucle** de récupération
  complémentaire sont déclarées explicitement, pas enfouies dans des `if` imbriqués ;
- chaque nœud est testable isolément et sa durée est tracée ;
- le graphe d'exécution est exportable (diagramme Mermaid du rapport).

Le workflow est déterministe : aucun nœud ne laisse le LLM choisir la suite du traitement.
"""

from __future__ import annotations

import operator
import time
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from core.llm import LLMClient
from core.settings import Settings
from expert_discovery.service import LIMITS as EXPERT_LIMITS
from expert_discovery.service import ExpertService
from extraction.referential import Referential
from knowledge_graph.client import Neo4jClient
from orchestration.classifier import Route, classify
from orchestration.conflicts import detect_conflicts
from orchestration.generator import (
    ABSTAIN_TEXT,
    ExtractiveGenerator,
    GenerationInput,
    LLMGenerator,
    generate_with_fallback,
)
from orchestration.sufficiency import TermStatistics, assess
from orchestration.verification import verify
from retrieval.access import AccessContext, AccessResolver
from retrieval.retriever import Retriever

MAX_EXPANSIONS = 1
FIXED_ROUTES = {
    "vector": Route("forced", "vector", 0.0, 1, "stratégie imposée : RAG vectoriel"),
    "lexical": Route("forced", "lexical", 0.0, 1, "stratégie imposée : BM25"),
    "hybrid": Route("forced", "hybrid", 0.0, 1, "stratégie imposée : RAG hybride"),
    "graph": Route("forced", "graph", 1.0, 2, "stratégie imposée : graphe seul"),
    "hybrid_graph": Route("forced", "hybrid_graph", 1.0, 2, "stratégie imposée : hybride + graphe (sans routage)"),
}


class QAState(TypedDict, total=False):
    question: str
    access: AccessContext
    allowed: list[str]
    strategy: str
    expansion_enabled: bool
    route: Route
    seeds: list[dict]
    ambiguous: list[dict]
    retrieval: Any
    attempts: int
    extra_seeds: list[str]
    extra_terms: list[str]
    sufficiency: Any
    conflicts: list
    experts: list
    generation: Any
    answer: str
    status: str
    verification: Any
    trace: Annotated[list[dict], operator.add]


class QAWorkflow:
    def __init__(self, settings: Settings, client: Neo4jClient, retriever: Retriever, access: AccessResolver,
                 experts: ExpertService, referential: Referential, llm: LLMClient, stats: TermStatistics) -> None:
        self.settings = settings
        self.client = client
        self.retriever = retriever
        self.access = access
        self.experts = experts
        self.ref = referential
        self.stats = stats
        self.llm_generator = LLMGenerator(llm) if settings.llm_enabled else None
        self.extractive = ExtractiveGenerator(stats)
        self.person_names = [e.name for e in referential.by_type("Person")]
        self.system_names = [n for e in referential.by_type("System") for n in e.all_surfaces]
        self.graph = self._build()

    # ------------------------------------------------------------------ nœuds
    def analyze(self, state: QAState) -> dict:
        t = time.perf_counter()
        seeds, ambiguous = self.retriever.graph.link_question(state["question"])
        if state.get("strategy", "auto") in FIXED_ROUTES:
            route = FIXED_ROUTES[state["strategy"]]
            classified = classify(state["question"], seeds, ambiguous)
            route = Route(classified.question_type, route.strategy, route.graph_weight, route.max_hops, route.reason)
        else:
            route = classify(state["question"], seeds, ambiguous)
        allowed = self.access.allowed_doc_ids(state["access"])
        return {"route": route, "seeds": seeds, "ambiguous": ambiguous, "allowed": allowed, "attempts": 0,
                "trace": [{"node": "analyze", "ms": _ms(t), "question_type": route.question_type,
                           "strategy": route.strategy, "reason": route.reason,
                           "entities": [s["id"] for s in seeds], "authorized_documents": len(allowed)}]}

    def retrieve(self, state: QAState) -> dict:
        t = time.perf_counter()
        route = state["route"]
        result = self.retriever.retrieve(
            state["question"], state["allowed"], route.strategy, k=self.settings.retrieval_top_k,
            graph_weight=route.graph_weight, max_hops=route.max_hops, extra_seeds=state.get("extra_seeds"),
            extra_terms=state.get("extra_terms"))
        return {"retrieval": result,
                "trace": [{"node": "retrieve", "ms": _ms(t), "attempt": state.get("attempts", 0) + 1,
                           "chunks": [c.id for c in result.chunks], "facts": len(result.graph.facts) if result.graph else 0,
                           "timings_ms": result.timings_ms}]}

    def assess_context(self, state: QAState) -> dict:
        t = time.perf_counter()
        retrieval = state["retrieval"]
        texts = [c.text for c in retrieval.chunks]
        # Les métadonnées du document (référence, version, statut) font partie du contexte.
        texts += [f"{c.title} {c.reference or ''} version {c.version or ''} "
                  f"{'version en vigueur' if c.status == 'active' else 'version remplacée'}" for c in retrieval.chunks]
        facts = retrieval.graph.facts[:10] if retrieval.graph else []
        texts += [f.text for f in facts]
        seed_surfaces = []
        for seed in state.get("seeds", []):
            if seed.get("ambiguous"):
                continue
            entity = self.ref.get(seed["id"])
            surfaces = [seed.get("surface") or ""] + ([entity.name] + entity.aliases if entity else [])
            seed_surfaces.append([x for x in surfaces if x])
        sufficiency = assess(state["question"], texts, seed_surfaces, self.stats, self.settings.sufficiency_threshold)
        conflicts = detect_conflicts(state["question"], retrieval.chunks)
        experts: list = []
        # Le classement de personnes est réservé au rôle manager, comme la page Experts (GET /api/experts).
        if state["route"].question_type == "expert" and state["access"].can("manager"):
            domain = self.experts.resolve_domain(state["question"])
            if domain:
                experts = [
                    {"person_id": e.person_id, "name": e.name, "score": e.score, "confidence": e.confidence,
                     "justification": e.justification,
                     "evidence": [ev.__dict__ for ev in e.evidence], "domain": domain}
                    for e in self.experts.find_experts(domain, state["allowed"], limit=5)]
                if experts and not sufficiency.sufficient:
                    sufficiency.sufficient = True
                    sufficiency.reason = "preuves d'expertise trouvées dans le graphe"
        return {"sufficiency": sufficiency, "conflicts": conflicts, "experts": experts,
                "trace": [{"node": "assess", "ms": _ms(t), "sufficient": sufficiency.sufficient,
                           "term_coverage": sufficiency.term_coverage, "entity_coverage": sufficiency.entity_coverage,
                           "reason": sufficiency.reason, "conflicts": [c.kind for c in conflicts]}]}

    def expand(self, state: QAState) -> dict:
        """Récupération complémentaire : graines enrichies des entités citées par les meilleurs
        passages, exploration plus profonde, termes de recherche enrichis des alias."""
        t = time.perf_counter()
        top_chunks = [c.id for c in state["retrieval"].chunks[:3]]
        rows = self.client.read(
            """UNWIND range(0, size($ids) - 1) AS i
               MATCH (c:Chunk {id: $ids[i]})-[:MENTIONS]->(e:Entity) WHERE NOT e:Domain
               WITH e.id AS id, min(i) AS first
               RETURN id ORDER BY first, id LIMIT 6""", ids=top_chunks)
        extra_seeds = [r["id"] for r in rows]
        extra_terms = []
        for seed in state.get("seeds", []):
            entity = self.ref.get(seed["id"])
            if entity:
                extra_terms += [entity.name] + entity.aliases[:2]
        route = state["route"]
        strategy = route.strategy
        if strategy in ("vector", "lexical", "hybrid") and state.get("strategy", "auto") == "auto":
            strategy = "hybrid_graph"
        new_route = Route(route.question_type, strategy, max(route.graph_weight, 1.0), 2,
                          route.reason + " ; récupération complémentaire")
        return {"route": new_route, "extra_seeds": extra_seeds, "extra_terms": extra_terms,
                "attempts": state.get("attempts", 0) + 1,
                "trace": [{"node": "expand", "ms": _ms(t), "extra_seeds": extra_seeds}]}

    def _generation_input(self, state: QAState) -> GenerationInput:
        retrieval = state["retrieval"]
        graph = retrieval.graph
        return GenerationInput(
            question=state["question"], question_type=state["route"].question_type, chunks=retrieval.chunks,
            facts=graph.facts[:10] if graph else [], conflicts=state.get("conflicts", []),
            ambiguous=state.get("ambiguous", []),
            seed_names=[s["surface"] for s in state.get("seeds", []) if s.get("surface")],
            intent_relations=graph.intent_relations if graph else [], paths=graph.paths if graph else [],
            person_names=self.person_names, system_names=self.system_names, experts=state.get("experts") or None,
            seed_ids=[s["id"] for s in state.get("seeds", [])])

    def generate(self, state: QAState) -> dict:
        t = time.perf_counter()
        output = generate_with_fallback(self._generation_input(state), self.llm_generator, self.extractive)
        return {"generation": output, "answer": output.text,
                "trace": [{"node": "generate", "ms": _ms(t), "generator": output.generator,
                           "llm_model": output.llm_model, "error": output.error}]}

    def abstain(self, state: QAState) -> dict:
        sufficiency = state["sufficiency"]
        consulted = list(dict.fromkeys(c.title for c in state["retrieval"].chunks[:4]))
        text = ABSTAIN_TEXT
        if sufficiency.missing_terms:
            text += f"\n\nÉléments non trouvés : {', '.join(sufficiency.missing_terms[:6])}."
        if consulted:
            text += "\n\nDocuments consultés sans réponse suffisante : " + " ; ".join(consulted) + "."
        return {"answer": text, "status": "abstained", "generation": None,
                "trace": [{"node": "abstain", "reason": sufficiency.reason}]}

    def verify_answer(self, state: QAState) -> dict:
        t = time.perf_counter()
        retrieval = state["retrieval"]
        sources = {f"C{i}": c.text for i, c in enumerate(retrieval.chunks, start=1)}
        for fact in (retrieval.graph.facts[:10] if retrieval.graph else []):
            sources[fact.id] = fact.text + " " + " ".join(fact.evidence_quotes)
        answer, report = verify(state["answer"], sources)
        generation = state["generation"]
        fallback = False
        if generation is not None and generation.generator.startswith("llm") and not report.abstention \
                and not report.valid_citations:
            # Réponse LLM sans aucune source valide : remplacée par la réponse extractive.
            output = self.extractive.generate(self._generation_input(state))
            answer, report = verify(output.text, sources)
            generation = output
            fallback = True
        status = "abstained" if report.abstention else "answered"
        return {"answer": answer, "verification": report, "status": status, "generation": generation,
                "trace": [{"node": "verify", "ms": _ms(t), "valid_citations": report.valid_citations,
                           "invalid_citations": report.invalid_citations, "support_rate": round(report.support_rate, 3),
                           "sanitized": report.sanitized, "fallback_extractive": fallback}]}

    # ------------------------------------------------------------------ graphe
    def _after_assess(self, state: QAState) -> str:
        if state["sufficiency"].sufficient:
            return "generate"
        if state.get("expansion_enabled", True) and state.get("attempts", 0) < MAX_EXPANSIONS:
            return "expand"
        return "abstain"

    def _build(self):
        builder = StateGraph(QAState)
        builder.add_node("analyze", self.analyze)
        builder.add_node("retrieve", self.retrieve)
        builder.add_node("assess", self.assess_context)
        builder.add_node("expand", self.expand)
        builder.add_node("generate", self.generate)
        builder.add_node("abstain", self.abstain)
        builder.add_node("verify", self.verify_answer)
        builder.add_edge(START, "analyze")
        builder.add_edge("analyze", "retrieve")
        builder.add_edge("retrieve", "assess")
        builder.add_conditional_edges("assess", self._after_assess,
                                      {"generate": "generate", "expand": "expand", "abstain": "abstain"})
        builder.add_edge("expand", "retrieve")
        builder.add_edge("generate", "verify")
        builder.add_edge("verify", END)
        builder.add_edge("abstain", END)
        return builder.compile()

    def mermaid(self) -> str:
        return self.graph.get_graph().draw_mermaid()

    # ------------------------------------------------------------------ API
    def run(self, question: str, access: AccessContext, strategy: str = "auto", expansion: bool = True) -> dict:
        started = time.perf_counter()
        state = self.graph.invoke({"question": question, "access": access, "strategy": strategy,
                                   "expansion_enabled": expansion, "trace": []})
        return build_response(state, round((time.perf_counter() - started) * 1000, 1), self.settings)


def _ms(t: float) -> float:
    return round((time.perf_counter() - t) * 1000, 1)


def build_response(state: QAState, total_ms: float, settings: Settings) -> dict:
    retrieval = state["retrieval"]
    answer = state.get("answer", "")
    verification = state.get("verification")
    cited = set(verification.valid_citations) if verification else set()
    citations = []
    for i, c in enumerate(retrieval.chunks, start=1):
        citations.append({
            "id": f"C{i}", "chunk_id": c.id, "doc_id": c.doc_id, "title": c.title, "reference": c.reference,
            "version": c.version, "date": c.doc_date, "status": c.status, "doc_type": c.doc_type,
            "section": c.section, "page": c.page, "text": c.text[:900], "cited": f"C{i}" in cited,
            "retrieval_ranks": c.ranks, "score": c.score})
    graph = retrieval.graph
    facts, nodes, edges = [], {}, []
    if graph:
        for f in graph.facts[:10]:
            facts.append({
                "id": f.id, "text": f.text, "relation": f.relation, "roles": f.roles, "confidence": f.confidence,
                "subject": {"id": f.subject_id, "name": f.subject_name, "type": f.subject_type},
                "object": {"id": f.object_id, "name": f.object_name, "type": f.object_type},
                "source_doc_ids": f.source_doc_ids,
                "evidence": [{"chunk_id": c, "quote": q} for c, q in zip(f.evidence_chunk_ids, f.evidence_quotes, strict=False)][:3],
                "cited": f.id in cited, "score": round(f.score, 4)})
            for ent in ((f.subject_id, f.subject_name, f.subject_type), (f.object_id, f.object_name, f.object_type)):
                nodes[ent[0]] = {"id": ent[0], "name": ent[1], "type": ent[2],
                                 "seed": ent[0] in {s["id"] for s in graph.seeds}}
            edges.append({"id": f.id, "source": f.subject_id, "target": f.object_id, "label": f.relation,
                          "cited": f.id in cited})
        for seed in graph.seeds:
            entity = graph.nodes.get(seed["id"])
            if entity and seed["id"] not in nodes:
                nodes[seed["id"]] = {**entity, "seed": True}
    limits = []
    generation = state.get("generation")
    if generation is not None and generation.generator == "extractive":
        limits.append("Mode hors-ligne : réponse extractive sans LLM (phrases reprises des documents, sans synthèse).")
    if generation is not None and generation.error:
        limits.append(generation.error)
    if any(c.status == "superseded" for c in retrieval.chunks):
        limits.append("Le contexte contient une version remplacée d'un document : la version en vigueur prévaut.")
    if state.get("experts"):
        limits.append(EXPERT_LIMITS)
    if verification and verification.unsupported:
        limits.append(f"{len(verification.unsupported)} phrase(s) de la réponse sans appui documentaire vérifié.")
    sufficiency = state.get("sufficiency")
    route = state["route"]
    return {
        "question": state["question"], "answer": answer, "status": state.get("status", "answered"),
        "question_type": route.question_type, "strategy": route.strategy, "route_reason": route.reason,
        "citations": citations, "facts": facts, "graph": {"nodes": list(nodes.values()), "edges": edges},
        "paths": graph.paths if graph else [],
        "conflicts": [c.message for c in state.get("conflicts", [])],
        "ambiguity": state.get("ambiguous", []), "experts": state.get("experts", []),
        "sufficiency": sufficiency.__dict__ if sufficiency else None,
        "verification": {"valid_citations": verification.valid_citations,
                         "invalid_citations": verification.invalid_citations,
                         "support_rate": round(verification.support_rate, 3),
                         "unsupported_sentences": verification.unsupported,
                         "sanitized": verification.sanitized} if verification else None,
        "generator": generation.generator if generation else None,
        "llm_model": generation.llm_model if generation else None,
        "limits": limits, "trace": state.get("trace", []), "latency_ms": total_ms,
        "llm_enabled": settings.llm_enabled,
    }
