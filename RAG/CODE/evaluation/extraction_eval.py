"""Évaluation de l'extraction de connaissances et de la résolution d'entités.

Comparaison au niveau du document : une relation extraite (sujet, type, objet) est correcte
si elle figure dans les annotations de référence du document. Les entités étant résolues
vers des identifiants canoniques, la comparaison ne dépend pas de la forme de surface
(cf. Wadhwa et al., 2023, sur les limites de la correspondance exacte de chaînes).

Deux sous-ensembles :
- développement (D01-D20) : utilisé pour mettre au point les règles ;
- test (D21-D35) : jamais consulté pendant la mise au point.
Les documents en doublon (D31, D32) et le document en quarantaine (D33) ont des annotations
vides : toute relation extraite y est un faux positif.

Usage : python -m evaluation.extraction_eval [--use-llm] [--show-errors dev|test]
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict

from core.llm import build_llm
from core.settings import CODE_DIR, get_settings
from evaluation.datasets import DEV_DOCS, TEST_DOCS, documents_dir, load_gold_documents, load_yaml
from extraction.linker import EntityLinker
from extraction.llm_extractor import LLMExtractor
from extraction.referential import load_referential
from extraction.resolver import EntityResolver
from extraction.rules import RuleExtractor
from ingestion.processor import DocumentProcessor

RESULTS_DIR = CODE_DIR / "evaluation" / "results"


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), "tp": tp, "fp": fp, "fn": fn}


def build_processor(use_llm: bool = False):
    settings = get_settings()
    ref = load_referential(settings.referentials_file)
    linker = EntityLinker(ref)
    rules = RuleExtractor(ref, CODE_DIR / "config" / "extraction_rules.yaml")
    llm_extractor = LLMExtractor(build_llm(settings), ref) if use_llm else None
    return DocumentProcessor(settings, ref, linker, rules, llm_extractor), ref


def evaluate_extraction(use_llm: bool = False) -> dict:
    processor, ref = build_processor(use_llm)
    gold = load_gold_documents()
    per_split: dict[str, Counter] = {"dev": Counter(), "test": Counter()}
    per_type: dict[str, dict[str, Counter]] = {"dev": defaultdict(Counter), "test": defaultdict(Counter)}
    mention_counts = {"dev": Counter(), "test": Counter()}
    errors: dict[str, list] = {"dev": [], "test": []}
    statuses = {}
    started = time.perf_counter()
    for gid, g in gold.items():
        split = "dev" if gid in DEV_DOCS else "test"
        doc = processor.process(documents_dir() / g.file_name, use_llm=use_llm)
        statuses[gid] = doc.record.status
        predicted = {(r.subject_id, r.relation, r.object_id) for r in doc.relations}
        if gid == "D31":  # doublon exact : détecté par le pipeline (empreinte) et non ré-extrait
            predicted = set()
        if gid == "D32":  # quasi-doublon : écarté par le pipeline (MinHash) avant écriture
            predicted = set()
        tp, fp, fn = predicted & g.relations, predicted - g.relations, g.relations - predicted
        per_split[split].update(tp=len(tp), fp=len(fp), fn=len(fn))
        for rel in tp:
            per_type[split][rel[1]]["tp"] += 1
        for rel in fp:
            per_type[split][rel[1]]["fp"] += 1
            errors[split].append({"doc": gid, "type": "FP", "relation": rel})
        for rel in fn:
            per_type[split][rel[1]]["fn"] += 1
            errors[split].append({"doc": gid, "type": "FN", "relation": rel})
        # Reconnaissance des entités (niveau document) : entités annotées vs entités liées.
        if doc.record.status == "active":
            found = {m.entity_id for ms in doc.mentions.values() for m in ms if m.entity_id}
            found |= set(doc.record.describes)
            gold_m = g.mentions
            mention_counts[split].update(tp=len(found & gold_m), fp=len(found - gold_m), fn=len(gold_m - found))

    report = {
        "extractor": "rules+llm" if use_llm else "rules",
        "duration_seconds": round(time.perf_counter() - started, 2),
        "relations": {s: prf(**{k: per_split[s][k] for k in ("tp", "fp", "fn")}) for s in per_split},
        "relations_by_type": {s: {t: prf(c["tp"], c["fp"], c["fn"]) for t, c in sorted(per_type[s].items())}
                              for s in per_type},
        "entity_mentions": {s: prf(mention_counts[s]["tp"], mention_counts[s]["fp"], mention_counts[s]["fn"])
                            for s in mention_counts},
        "document_status": statuses,
        "llm_stats": dict(processor.llm.stats) if processor.llm else None,
    }
    report["_errors"] = errors
    return report


def evaluate_entity_resolution() -> dict:
    settings = get_settings()
    ref = load_referential(settings.referentials_file)
    resolver = EntityResolver(ref)
    cases = load_yaml("entity_resolution_gold.yaml")["cases"]
    from core.text import normalize_key

    known_surfaces = {normalize_key(s) for e in ref.entities.values() for s in e.all_surfaces}
    groups: dict[str, Counter] = defaultdict(Counter)
    details = []
    for case in cases:
        res = resolver.resolve(case["mention"], case.get("type"), case["context"])
        expected = case["expected"]
        correct = res.entity_id == expected
        if expected is None:
            group = "negatif (aucune entite attendue)"
        elif normalize_key(case["mention"]) in known_surfaces:
            group = "alias present au referentiel"
        else:
            group = "variante absente du referentiel"
        groups[group]["correct" if correct else "wrong"] += 1
        groups["global"]["correct" if correct else "wrong"] += 1
        details.append({"mention": case["mention"], "expected": expected, "predicted": res.entity_id,
                        "method": res.method, "score": res.score, "correct": correct, "group": group})
    return {
        "accuracy_by_group": {g: {"accuracy": round(c["correct"] / (c["correct"] + c["wrong"]), 3),
                                  "n": c["correct"] + c["wrong"]} for g, c in groups.items()},
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--show-errors", choices=["dev", "test"], default=None)
    args = parser.parse_args()
    report = evaluate_extraction(use_llm=args.use_llm)
    errors = report.pop("_errors")
    er = evaluate_entity_resolution()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    name = "extraction_rules_llm.json" if args.use_llm else "extraction_rules.json"
    (RESULTS_DIR / name).write_text(json.dumps({**report, "entity_resolution": er}, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("relations", "entity_mentions")}, indent=2))
    for split in ("dev", "test"):
        print(split, {t: (v["precision"], v["recall"]) for t, v in report["relations_by_type"][split].items()})
    print("Résolution d'entités :", er["accuracy_by_group"])
    if args.show_errors:
        for e in sorted(errors[args.show_errors], key=lambda x: (x["doc"], x["type"])):
            print(e["doc"], e["type"], e["relation"])


if __name__ == "__main__":
    main()
