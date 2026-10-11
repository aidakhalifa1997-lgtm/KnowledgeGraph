"""Évaluation expérimentale reproductible de la plateforme.

Usage (depuis RAG/CODE, base Neo4j configurée par les variables NEO4J_*) :

    python -m evaluation.run_evaluation --reingest            # campagne complète
    python -m evaluation.run_evaluation --sections retrieval  # une seule section
    EMBEDDING_PROVIDER=wordllama python -m evaluation.run_evaluation --reingest \
        --sections ingestion,retrieval --tag wordllama        # ablation de l'encodeur

Sections :
- ingestion       : reconstruction complète de la base, durées par étape, ré-exécution idempotente ;
- kg              : qualité structurelle du graphe (volumes, provenance, confiance) ;
- extraction      : précision / rappel de l'extraction de relations et résolution d'entités ;
- retrieval       : classement des documents pour 6 stratégies (vector, lexical, hybrid, graph,
                    hybrid_graph, auto) : Recall@k, Precision@k, MRR, nDCG@k, couverture des preuves ;
- qa              : bout en bout via le workflow LangGraph pour 5 architectures : exactitude,
                    abstention, contradictions, ambiguïtés, citations, fuites d'accès, latence ;
- ablations       : sensibilité au seuil de suffisance, workflow sans récupération complémentaire ;
- experts         : classement d'experts vs baseline « nombre de mentions » ;
- recommendations : modes contenu / graphe / hybride.

Les résultats bruts (par question) et agrégés sont écrits dans evaluation/results/<tag>/.
Aucun résultat n'est saisi à la main : tout chiffre du rapport provient de ces fichiers.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from backend.security import UserStore
from core.logging_config import configure_logging
from core.settings import CODE_DIR, get_settings
from core.text import normalize_key
from evaluation.datasets import load_gold_documents, load_questions, load_yaml
from evaluation.metrics import paired_comparison, percentile, ranking_metrics, safe_ratio, summarize
from ingestion.processor import document_id_for
from orchestration.classifier import classify
from orchestration.workflow import QAWorkflow
from retrieval.access import AccessContext
from services import Services, build_services

RESULTS_ROOT = CODE_DIR / "evaluation" / "results"
RETRIEVAL_STRATEGIES = ["vector", "lexical", "hybrid", "graph", "hybrid_graph", "auto"]
QA_ARCHITECTURES = {
    "rag_vectoriel": "vector",
    "rag_hybride": "hybrid",
    "graphrag": "graph",
    "hybride_graphe_fixe": "hybrid_graph",
    "hybride_final": "auto",
}
THRESHOLDS = [0.35, 0.45, 0.55, 0.65, 0.75]
ALL_SECTIONS = ["ingestion", "kg", "extraction", "retrieval", "qa", "ablations", "experts", "recommendations"]


# ---------------------------------------------------------------------------- utilitaires
def _round(x, n=4):
    return None if x is None else round(x, n)


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})


def _contains(text: str, needle: str) -> bool:
    """Présence d'une expression dans un texte, insensible à la casse et aux accents, avec une
    frontière à gauche (« 25 » ne correspond pas à « 2025 »)."""
    return re.search(r"(?<!\w)" + re.escape(normalize_key(needle)), normalize_key(text)) is not None


def _latency(values: list[float]) -> dict:
    if not values:
        return {}
    return {"mean_ms": round(statistics.fmean(values), 1), "p50_ms": round(percentile(values, 0.5), 1),
            "p95_ms": round(percentile(values, 0.95), 1), "max_ms": round(max(values), 1)}


class Context:
    def __init__(self, services: Services) -> None:
        self.services = services
        gold_docs = load_gold_documents()
        self.gold_to_doc = {g.doc_id: document_id_for(g.file_name) for g in gold_docs.values()}
        self.doc_to_gold = {v: k for k, v in self.gold_to_doc.items()}
        questions_file = load_yaml("questions.yaml")
        self.dev_questions = set(questions_file.get("development_questions", []))
        self.questions = load_questions()
        store = UserStore(services.settings.users_file)
        self.users = {u.username: AccessContext(u.username, u.groups, u.roles) for u in store.users.values()}
        self._allowed: dict[str, list[str]] = {}

    def allowed(self, username: str) -> list[str]:
        if username not in self._allowed:
            self._allowed[username] = self.services.access.allowed_doc_ids(self.users[username])
        return self._allowed[username]

    def relevance(self, question: dict) -> dict[str, int]:
        return {self.gold_to_doc[d]: int(r) for d, r in (question.get("gold_docs") or {}).items()}

    def split(self, question: dict) -> str:
        return "developpement" if question["id"] in self.dev_questions else "jamais_inspectee"


# ---------------------------------------------------------------------------- sections
def run_ingestion(ctx: Context) -> dict:
    services = ctx.services
    services.repository.reset()
    services.ensure_schema()
    started = time.perf_counter()
    report = services.pipeline.sync_directory(services.settings.documents_dir)
    full = time.perf_counter() - started
    services.refresh_after_ingestion()
    started = time.perf_counter()
    rerun = services.pipeline.sync_directory(services.settings.documents_dir)
    idempotent = time.perf_counter() - started
    stages: dict[str, list[float]] = defaultdict(list)
    for result in report.results:
        for timing in result.timings:
            stages[timing.stage].append(timing.seconds)
    by_format: dict[str, list[float]] = defaultdict(list)
    for result in report.results:
        total = sum(t.seconds for t in result.timings)
        by_format[Path(result.file_name).suffix.lower()].append(total)
    final_status = Counter(r["s"] for r in services.client.read("MATCH (d:Document) RETURN d.status AS s"))
    return {
        "files": report.files_seen,
        "outcomes_at_ingestion": dict(Counter(r.outcome for r in report.results)),
        "final_document_status": dict(final_status),
        "full_ingestion_seconds": round(full, 2),
        "idempotent_rerun_seconds": round(idempotent, 2),
        "idempotent_rerun_unchanged": rerun.count("unchanged"),
        "stage_seconds_total": {k: round(sum(v), 2) for k, v in stages.items()},
        "stage_seconds_mean_per_document": {k: round(statistics.fmean(v), 3) for k, v in stages.items()},
        "processing_seconds_by_format": {k: {"n": len(v), "mean": round(statistics.fmean(v), 3)}
                                         for k, v in by_format.items()},
        "chunks": sum(r.chunks for r in report.results),
        "relations_extracted": sum(r.relations for r in report.results),
        "quality_issues": dict(Counter(i.code for r in report.results for i in r.issues)),
    }


def run_kg(ctx: Context) -> dict:
    client = ctx.services.client
    nodes = {r["label"]: r["n"] for r in client.read(
        "MATCH (n) UNWIND labels(n) AS label WITH label, count(*) AS n WHERE label <> 'Entity' RETURN label, n")}
    rels = {r["t"]: r["n"] for r in client.read("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n ORDER BY n DESC")}
    extracted = client.read(
        """MATCH ()-[r]->() WHERE r.source = 'extracted'
           RETURN count(r) AS n,
                  sum(CASE WHEN size(coalesce(r.evidence_chunk_ids, [])) > 0 AND size(coalesce(r.source_doc_ids, [])) > 0
                           THEN 1 ELSE 0 END) AS with_provenance,
                  avg(r.confidence) AS mean_confidence,
                  avg(size(r.source_doc_ids)) AS mean_sources,
                  sum(CASE WHEN size(r.source_doc_ids) >= 2 THEN 1 ELSE 0 END) AS multi_source""")[0]
    # Combinaison d'extracteurs ayant produit chaque relation (« rules », « llm », « llm+rules »).
    extractors = {r["e"]: r["n"] for r in client.read(
        """MATCH ()-[r]->() WHERE r.source = 'extracted'
           WITH reduce(s = '', x IN coalesce(r.extractors, []) | s + (CASE WHEN s = '' THEN '' ELSE '+' END) + x) AS e
           RETURN e, count(*) AS n""")}
    entities = client.read(
        """MATCH (e:Entity) WHERE NOT e:Domain AND NOT e:Concept
           OPTIONAL MATCH (e)-[r]-(:Entity)
           WITH e, count(r) AS degree RETURN count(e) AS n, avg(degree) AS mean_degree,
           sum(CASE WHEN degree = 0 THEN 1 ELSE 0 END) AS isolated""")[0]
    candidates = client.read("MATCH (e:Entity {status: 'candidate'}) RETURN count(e) AS n")
    return {
        "nodes_by_label": nodes, "relationships_by_type": rels,
        "extracted_relations": extracted["n"],
        "provenance_coverage": _round(safe_ratio(extracted["with_provenance"], extracted["n"])),
        "mean_confidence": _round(extracted["mean_confidence"], 3),
        "mean_source_documents_per_relation": _round(extracted["mean_sources"], 3),
        "relations_supported_by_2plus_documents": extracted["multi_source"],
        "relations_by_extractor": extractors,
        "entities_excluding_taxonomy": entities["n"], "mean_entity_degree": _round(entities["mean_degree"], 2),
        "isolated_entities": entities["isolated"],
        "candidate_entities_pending_review": candidates[0]["n"] if candidates else 0,
    }


def run_extraction(ctx: Context) -> dict:
    from evaluation.extraction_eval import evaluate_entity_resolution, evaluate_extraction

    report = evaluate_extraction(use_llm=False)
    report.pop("_errors", None)
    return {**report, "entity_resolution": evaluate_entity_resolution()}


def _retrieve(ctx: Context, question: dict, strategy: str):
    services = ctx.services
    allowed = ctx.allowed(question["user"])
    if strategy == "auto":
        seeds, ambiguous = services.graph_retriever.link_question(question["question"])
        route = classify(question["question"], seeds, ambiguous)
        return services.retriever.retrieve(question["question"], allowed, route.strategy,
                                           k=services.settings.retrieval_top_k, graph_weight=route.graph_weight,
                                           max_hops=route.max_hops)
    hops = 2 if strategy in ("graph", "hybrid_graph") else 1
    return services.retriever.retrieve(question["question"], allowed, strategy, k=services.settings.retrieval_top_k,
                                       graph_weight=1.0, max_hops=hops)


def run_retrieval(ctx: Context) -> tuple[dict, list[dict]]:
    rows = []
    questions = [q for q in ctx.questions if q.get("gold_docs") and not q.get("expected_abstain")]
    for strategy in RETRIEVAL_STRATEGIES:
        for q in questions:
            started = time.perf_counter()
            result = _retrieve(ctx, q, strategy)
            ms = (time.perf_counter() - started) * 1000
            relevance = ctx.relevance(q)
            ranking = result.doc_ranking
            context = " ".join(c.text for c in result.chunks)
            if result.graph:
                context += " " + " ".join(f.text + " " + " ".join(f.evidence_quotes) for f in result.graph.facts[:10])
            evidence = q.get("evidence") or []
            leaked = [d for d in ranking if d not in set(ctx.allowed(q["user"]))]
            rows.append({
                "question": q["id"], "category": q["category"], "split": ctx.split(q), "strategy": strategy,
                **{k: round(v, 4) for k, v in ranking_metrics(ranking, relevance).items()},
                "evidence_recall": round(sum(_contains(context, e) for e in evidence) / len(evidence), 4) if evidence else None,
                "ranking": [ctx.doc_to_gold.get(d, d) for d in ranking], "latency_ms": round(ms, 1),
                "leaked_documents": len(leaked),
            })
    return _aggregate_retrieval(rows), rows


def _aggregate_retrieval(rows: list[dict]) -> dict:
    metrics = ["recall@1", "recall@3", "recall@5", "precision@1", "precision@3", "precision@5", "mrr", "ndcg@3",
               "ndcg@5", "evidence_recall"]
    by_strategy: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_strategy[row["strategy"]].append(row)
    summary: dict = {"n_questions": len({r["question"] for r in rows}), "strategies": {}, "by_category": {},
                     "by_split": {}, "paired_vs_vector": {}, "paired_vs_hybrid": {}}
    for strategy, items in by_strategy.items():
        summary["strategies"][strategy] = {
            **{m: summarize([r[m] for r in items if r[m] is not None]) for m in metrics},
            "latency": _latency([r["latency_ms"] for r in items]),
            "leaked_documents": sum(r["leaked_documents"] for r in items)}
        categories = sorted({r["category"] for r in items})
        summary["by_category"][strategy] = {
            c: {m: _round(statistics.fmean([r[m] for r in items if r["category"] == c])) for m in ("recall@5", "ndcg@5", "mrr")}
            | {"n": sum(1 for r in items if r["category"] == c)} for c in categories}
        summary["by_split"][strategy] = {
            s: {m: summarize([r[m] for r in items if r["split"] == s]) for m in ("recall@5", "ndcg@5", "mrr")}
            for s in ("developpement", "jamais_inspectee")}
    for base in ("vector", "hybrid"):
        reference = {r["question"]: r for r in by_strategy.get(base, [])}
        for strategy, items in by_strategy.items():
            if strategy == base:
                continue
            a = [r["ndcg@5"] for r in items]
            b = [reference[r["question"]]["ndcg@5"] for r in items]
            summary[f"paired_vs_{base}"][strategy] = {"metric": "ndcg@5", **paired_comparison(a, b)}
    return summary


def _qa_row(ctx: Context, q: dict, architecture: str, response: dict, ms: float) -> dict:
    answer = response["answer"]
    abstained = response["status"] == "abstained"
    groups = q.get("answer_keywords") or []
    hits = [any(_contains(answer, alt) for alt in group) for group in groups]
    forbidden_hit = [f for f in q.get("forbidden") or [] if _contains(answer, f)]
    if q.get("expected_abstain"):
        correct = abstained and not forbidden_hit
    else:
        correct = (not abstained) and all(hits) and not forbidden_hit
    relevance = ctx.relevance(q)
    cited = [c for c in response["citations"] if c["cited"]]
    cited_docs = list(dict.fromkeys(c["doc_id"] for c in cited))
    allowed = set(ctx.allowed(q["user"]))
    context_docs = list(dict.fromkeys(c["doc_id"] for c in response["citations"]))
    leaks = [d for d in context_docs + [d for f in response["facts"] for d in f["source_doc_ids"]] if d not in allowed]
    verification = response.get("verification") or {}
    nodes = [t["node"] for t in response["trace"]]
    return {
        "question": q["id"], "category": q["category"], "split": ctx.split(q), "architecture": architecture,
        "user": q["user"], "status": response["status"], "expected_abstain": bool(q.get("expected_abstain")),
        "correct": int(correct), "keyword_groups": len(groups), "keyword_groups_hit": sum(hits),
        "forbidden_hit": forbidden_hit,
        "expect_conflict": bool(q.get("expect_conflict")), "conflict_flagged": int(bool(response["conflicts"])),
        "expect_ambiguity": bool(q.get("expect_ambiguity")),
        "ambiguity_flagged": int(bool(response["ambiguity"]) or response["question_type"] == "ambiguous"),
        "question_type": response["question_type"], "generator": response["generator"],
        "valid_citations": len(verification.get("valid_citations", [])),
        "invalid_citations": len(verification.get("invalid_citations", [])),
        "support_rate": verification.get("support_rate"),
        "unsupported_sentences": len(verification.get("unsupported_sentences", [])),
        "cited_documents": [ctx.doc_to_gold.get(d, d) for d in cited_docs],
        "citation_precision": _round(safe_ratio(sum(1 for d in cited_docs if relevance.get(d, 0) > 0), len(cited_docs)))
        if relevance and cited_docs else None,
        "cites_essential_document": int(any(relevance.get(d, 0) == 2 for d in cited_docs)) if relevance else None,
        **({f"context_{k}": round(v, 4) for k, v in ranking_metrics(context_docs, relevance, ks=(5,)).items()}
           if relevance and not q.get("expected_abstain") else {}),
        "access_leaks": len(leaks), "expansion": int("expand" in nodes), "latency_ms": round(ms, 1),
        "answer": answer[:600],
    }


def run_qa_workflow(ctx: Context, workflow: QAWorkflow, architecture: str, strategy: str,
                    expansion: bool = True) -> list[dict]:
    rows = []
    for q in ctx.questions:
        started = time.perf_counter()
        response = workflow.run(q["question"], ctx.users[q["user"]], strategy=strategy, expansion=expansion)
        rows.append(_qa_row(ctx, q, architecture, response, (time.perf_counter() - started) * 1000))
    return rows


def _aggregate_qa(rows: list[dict]) -> dict:
    out: dict = {}
    by_arch: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_arch[row["architecture"]].append(row)
    for arch, items in by_arch.items():
        answerable = [r for r in items if not r["expected_abstain"]]
        unanswerable = [r for r in items if r["expected_abstain"]]
        abstained = [r for r in items if r["status"] == "abstained"]
        conflict_q = [r for r in items if r["expect_conflict"]]
        no_conflict_q = [r for r in items if not r["expect_conflict"]]
        amb_q = [r for r in items if r["expect_ambiguity"]]
        out[arch] = {
            "n": len(items),
            "accuracy_overall": summarize([r["correct"] for r in items]),
            "accuracy_answerable": summarize([r["correct"] for r in answerable]),
            "accuracy_by_split": {s: summarize([r["correct"] for r in items if r["split"] == s])
                                  for s in ("developpement", "jamais_inspectee")},
            "accuracy_by_category": {c: _round(statistics.fmean([r["correct"] for r in items if r["category"] == c]))
                                     for c in sorted({r["category"] for r in items})},
            "abstention_recall": _round(safe_ratio(sum(1 for r in unanswerable if r["status"] == "abstained"),
                                                   len(unanswerable))),
            "abstention_precision": _round(safe_ratio(sum(1 for r in abstained if r["expected_abstain"]), len(abstained))),
            "false_abstention_rate": _round(safe_ratio(sum(1 for r in answerable if r["status"] == "abstained"),
                                                       len(answerable))),
            "conflict_recall": _round(safe_ratio(sum(r["conflict_flagged"] for r in conflict_q), len(conflict_q))),
            "conflict_false_positive_rate": _round(safe_ratio(sum(r["conflict_flagged"] for r in no_conflict_q
                                                                  if r["status"] == "answered"),
                                                              sum(1 for r in no_conflict_q if r["status"] == "answered"))),
            "ambiguity_recall": _round(safe_ratio(sum(r["ambiguity_flagged"] for r in amb_q), len(amb_q))),
            "invalid_citations_total": sum(r["invalid_citations"] for r in items),
            "support_rate_mean": _round(statistics.fmean([r["support_rate"] for r in items
                                                          if r["support_rate"] is not None and r["status"] == "answered"]
                                                         or [0])),
            "citation_precision_mean": _round(statistics.fmean([r["citation_precision"] for r in items
                                                                if r["citation_precision"] is not None] or [0])),
            "cites_essential_document_rate": _round(statistics.fmean([r["cites_essential_document"] for r in answerable
                                                                      if r["cites_essential_document"] is not None
                                                                      and r["status"] == "answered"] or [0])),
            "context_recall@5": summarize([r["context_recall@5"] for r in items if "context_recall@5" in r]),
            "context_ndcg@5": summarize([r["context_ndcg@5"] for r in items if "context_ndcg@5" in r]),
            "forbidden_violations": sum(1 for r in items if r["forbidden_hit"]),
            "access_leaks": sum(r["access_leaks"] for r in items),
            "expansion_rate": _round(statistics.fmean([r["expansion"] for r in items])),
            "latency": _latency([r["latency_ms"] for r in items]),
        }
    final = {r["question"]: r for r in by_arch.get("hybride_final", [])}
    if final:
        out["paired_vs_hybride_final"] = {}
        for arch, items in by_arch.items():
            if arch == "hybride_final":
                continue
            a = [final[r["question"]]["correct"] for r in items]
            b = [r["correct"] for r in items]
            out["paired_vs_hybride_final"][arch] = {"metric": "correct (hybride_final - autre)",
                                                    **paired_comparison(a, b)}
    return out


def _classifier_agreement(rows: list[dict]) -> dict:
    mapping = {"factual": "factual", "relational": "relational", "multi_hop": "multi_hop", "expert": "expert",
               "ambiguous": "ambiguous"}
    items = [r for r in rows if r["architecture"] == "hybride_final" and r["category"] in mapping]
    confusion: dict[str, Counter] = defaultdict(Counter)
    for r in items:
        confusion[r["category"]][r["question_type"]] += 1
    agree = sum(1 for r in items if mapping[r["category"]] == r["question_type"])
    return {"n": len(items), "agreement": _round(safe_ratio(agree, len(items))),
            "confusion": {k: dict(v) for k, v in confusion.items()}}


def run_qa(ctx: Context) -> tuple[dict, list[dict]]:
    rows = []
    workflow = ctx.services.workflow
    for architecture, strategy in QA_ARCHITECTURES.items():
        rows += run_qa_workflow(ctx, workflow, architecture, strategy)
    summary = _aggregate_qa(rows)
    summary["classifier_agreement"] = _classifier_agreement(rows)
    summary["generator"] = "extractif (hors-ligne)" if not ctx.services.settings.llm_enabled else "llm"
    return summary, rows


def run_ablations(ctx: Context) -> tuple[dict, list[dict]]:
    services = ctx.services
    rows = []
    for threshold in THRESHOLDS:
        settings = services.settings.model_copy(update={"sufficiency_threshold": threshold})
        workflow = QAWorkflow(settings, services.client, services.retriever, services.access, services.experts,
                              services.referential, services.llm, services.term_stats)
        rows += run_qa_workflow(ctx, workflow, f"seuil_{threshold:.2f}", "auto")
    rows += run_qa_workflow(ctx, services.workflow, "sans_relance", "auto", expansion=False)
    summary = _aggregate_qa(rows)
    summary.pop("paired_vs_hybride_final", None)
    return summary, rows


def run_experts(ctx: Context) -> dict:
    gold = load_yaml("experts_gold.yaml")["domains"]
    allowed = ctx.allowed("admin")
    per_domain, ours, baseline = {}, defaultdict(list), defaultdict(list)
    for domain, relevance in gold.items():
        ranking = [r.person_id for r in ctx.services.experts.find_experts(domain, allowed, limit=10)]
        base = [pid for pid, _ in ctx.services.experts.mention_baseline(domain, allowed, limit=10)]
        m_ours, m_base = ranking_metrics(ranking, relevance, ks=(1, 3)), ranking_metrics(base, relevance, ks=(1, 3))
        false_top3 = sum(1 for p in ranking[:3] if relevance.get(p, 0) == 0)
        false_top3_base = sum(1 for p in base[:3] if relevance.get(p, 0) == 0)
        per_domain[domain] = {"ours": ranking[:5], "baseline": base[:5], "gold": relevance,
                              "ours_metrics": {k: round(v, 4) for k, v in m_ours.items()},
                              "baseline_metrics": {k: round(v, 4) for k, v in m_base.items()},
                              "non_experts_in_top3": {"ours": false_top3, "baseline": false_top3_base}}
        for k in ("precision@1", "recall@3", "ndcg@3", "mrr"):
            ours[k].append(m_ours[k])
            baseline[k].append(m_base[k])
    return {
        "n_domains": len(gold),
        "ours": {k: summarize(v) for k, v in ours.items()},
        "baseline_mentions": {k: summarize(v) for k, v in baseline.items()},
        "paired_ndcg@3": paired_comparison(ours["ndcg@3"], baseline["ndcg@3"]),
        "non_experts_in_top3_total": {"ours": sum(d["non_experts_in_top3"]["ours"] for d in per_domain.values()),
                                      "baseline": sum(d["non_experts_in_top3"]["baseline"] for d in per_domain.values())},
        "per_domain": per_domain,
    }


def run_recommendations(ctx: Context) -> dict:
    gold = load_yaml("recommendations_gold.yaml")
    forbidden = {ctx.gold_to_doc[d] for d in gold["forbidden"]}
    allowed = ctx.allowed("admin")
    out: dict = {"n_sources": len(gold["queries"]), "modes": {}}
    for mode in ("content", "graph", "hybrid"):
        metrics, per_source, violations = defaultdict(list), {}, 0
        for source, rel in gold["queries"].items():
            relevance = {ctx.gold_to_doc[d]: int(r) for d, r in rel.items()}
            items = ctx.services.recommendations.for_document(ctx.gold_to_doc[source], allowed, limit=5, mode=mode)
            ranking = [i.doc_id for i in items]
            violations += sum(1 for d in ranking if d in forbidden)
            m = ranking_metrics(ranking, relevance, ks=(3, 5))
            per_source[source] = {"ranking": [ctx.doc_to_gold.get(d, d) for d in ranking],
                                  **{k: round(v, 4) for k, v in m.items()}}
            for k in ("precision@5", "recall@5", "ndcg@5", "mrr"):
                metrics[k].append(m[k])
        out["modes"][mode] = {**{k: summarize(v) for k, v in metrics.items()}, "forbidden_recommended": violations,
                              "per_source": per_source}
    hybrid, content = out["modes"]["hybrid"]["per_source"], out["modes"]["content"]["per_source"]
    out["paired_hybrid_vs_content_ndcg@5"] = paired_comparison([hybrid[s]["ndcg@5"] for s in hybrid],
                                                               [content[s]["ndcg@5"] for s in hybrid])
    return out


def environment(services: Services, tag: str) -> dict:
    git = shutil.which("git")
    commit, dirty = None, None
    if git:  # arguments constants : aucune entrée externe
        commit = subprocess.run([git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True,  # noqa: S603
                                cwd=CODE_DIR, check=False).stdout.strip()
        status = subprocess.run([git, "status", "--porcelain", "--", "."], capture_output=True, text=True,  # noqa: S603
                                cwd=CODE_DIR, check=False).stdout
        # Seuls les fichiers de code comptent (les résultats eux-mêmes sont réécrits par la campagne).
        dirty = any(line and "evaluation/results/" not in line for line in status.splitlines())
    version = services.client.read("CALL dbms.components() YIELD name, versions, edition "
                                   "RETURN name, versions[0] AS version, edition")
    return {"tag": tag, "date": datetime.now(UTC).isoformat(timespec="seconds"), "git_commit": commit,
            "code_modified_since_commit": dirty, "source_guarantee": services.settings.retrieval_source_guarantee,
            "python": platform.python_version(), "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "neo4j": version[0] if version else None, "embedding_provider": services.settings.embedding_provider,
            "embedding_dim": services.embedder.dim, "llm_enabled": services.settings.llm_enabled,
            "retrieval_top_k": services.settings.retrieval_top_k, "rrf_k": services.settings.rrf_k,
            "sufficiency_threshold": services.settings.sufficiency_threshold}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reingest", action="store_true", help="vider la base et réingérer le corpus (section ingestion)")
    parser.add_argument("--sections", default=",".join(ALL_SECTIONS))
    parser.add_argument("--tag", default=None, help="sous-dossier de résultats (par défaut : encodeur utilisé)")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging("WARNING")
    services = build_services(settings)
    tag = args.tag or settings.embedding_provider
    out = RESULTS_ROOT / tag
    out.mkdir(parents=True, exist_ok=True)
    sections = [s.strip() for s in args.sections.split(",") if s.strip()]
    if args.reingest and "ingestion" not in sections:
        sections.insert(0, "ingestion")
    ctx = Context(services)
    _write_json(out / "environment.json", environment(services, tag))
    for section in sections:
        started = time.perf_counter()
        print(f"[évaluation] section {section}…", flush=True)
        if section == "ingestion":
            if not args.reingest:
                print("  ignorée (utiliser --reingest)")
                continue
            _write_json(out / "ingestion.json", run_ingestion(ctx))
            ctx = Context(services)
        elif section == "kg":
            _write_json(out / "kg_quality.json", run_kg(ctx))
        elif section == "extraction":
            _write_json(out / "extraction.json", run_extraction(ctx))
        elif section == "retrieval":
            summary, rows = run_retrieval(ctx)
            _write_json(out / "retrieval_summary.json", summary)
            _write_csv(out / "retrieval_per_question.csv", rows)
        elif section == "qa":
            summary, rows = run_qa(ctx)
            _write_json(out / "qa_summary.json", summary)
            _write_csv(out / "qa_per_question.csv", rows)
        elif section == "ablations":
            summary, rows = run_ablations(ctx)
            _write_json(out / "ablations_summary.json", summary)
            _write_csv(out / "ablations_per_question.csv", rows)
        elif section == "experts":
            _write_json(out / "experts.json", run_experts(ctx))
        elif section == "recommendations":
            _write_json(out / "recommendations.json", run_recommendations(ctx))
        else:
            raise SystemExit(f"section inconnue : {section}")
        print(f"  terminée en {time.perf_counter() - started:.1f} s", flush=True)
    services.close()
    print(f"Résultats écrits dans {out}")


if __name__ == "__main__":
    main()
