"""Audit complémentaire du contrôle d'accès.

La campagne principale pose 62 des 66 questions avec le compte administrateur (seules les
questions de la catégorie « accès » changent de compte). Cet audit rejoue TOUTES les questions avec
des comptes restreints, pour chaque architecture, et vérifie qu'aucun document non autorisé
n'apparaît dans le contexte (passages), dans les faits du graphe ni dans le classement d'experts.

Usage (base Neo4j contenant le corpus ingéré) :
    NEO4J_URI=... NEO4J_PASSWORD=... python -m evaluation.access_audit --tag audit_acces
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from core.settings import DATA_DIR
from evaluation.run_evaluation import QA_ARCHITECTURES
from retrieval.access import AccessContext
from services import build_services

RESULTS_DIR = Path(__file__).resolve().parent / "results"
ACCOUNTS = {
    "collaborateur": AccessContext("collaborateur", frozenset({"ALL"}), frozenset({"viewer"})),
    "analyste.conformite": AccessContext("analyste.conformite", frozenset({"ALL", "DCONF"}), frozenset({"viewer"})),
    "ingenieur.dsi": AccessContext("ingenieur.dsi", frozenset({"ALL", "DSI"}), frozenset({"viewer"})),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit du contrôle d'accès avec des comptes restreints")
    parser.add_argument("--tag", default="audit_acces")
    args = parser.parse_args()

    services = build_services()
    questions = yaml.safe_load((DATA_DIR / "synthetic_data" / "gold" / "questions.yaml").read_text(encoding="utf-8"))
    runs, leaks, restricted_seen = 0, [], 0
    for username, access in ACCOUNTS.items():
        allowed = set(services.access.allowed_doc_ids(access))
        for architecture, strategy in QA_ARCHITECTURES.items():
            for q in questions["questions"]:
                response = services.workflow.run(q["question"], access, strategy=strategy)
                runs += 1
                docs = {c["doc_id"] for c in response["citations"]}
                docs |= {d for f in response["facts"] for d in f["source_doc_ids"]}
                docs |= {ev["doc_id"] for e in response["experts"] for ev in e.get("evidence", []) if ev.get("doc_id")}
                bad = sorted(docs - allowed)
                if bad:
                    leaks.append({"user": username, "architecture": architecture, "question": q["id"], "documents": bad})
                restricted_seen += int(bool(response["experts"]))
    summary = {"accounts": list(ACCOUNTS), "architectures": list(QA_ARCHITECTURES), "questions": len(questions["questions"]),
               "runs": runs, "runs_with_leak": len(leaks), "leaks": leaks,
               "runs_with_expert_ranking_for_viewers": restricted_seen}
    out = RESULTS_DIR / args.tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "access_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "leaks"}, ensure_ascii=False))
    services.close()


if __name__ == "__main__":
    main()
