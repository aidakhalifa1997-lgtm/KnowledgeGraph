"""Ingestion en ligne de commande.

Exemples :
    python -m scripts.ingest                      # synchronise data/sample_documents
    python -m scripts.ingest --reset              # vide le graphe puis réingère tout
    python -m scripts.ingest --dir /chemin/docs --no-delete
    python -m scripts.ingest --use-llm            # extraction LLM en plus des règles
"""

from __future__ import annotations

import argparse
import json

from core.logging_config import configure_logging
from services import build_services


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion des documents dans le Knowledge Graph")
    parser.add_argument("--dir", default=None, help="répertoire source (défaut : DOCUMENTS_DIR)")
    parser.add_argument("--reset", action="store_true", help="vider le graphe avant ingestion")
    parser.add_argument("--no-delete", action="store_true", help="ne pas supprimer les documents absents du répertoire")
    parser.add_argument("--use-llm", action="store_true", help="activer l'extraction par LLM (clé requise)")
    args = parser.parse_args()

    services = build_services()
    configure_logging(services.settings.log_level)
    if not services.client.ping():
        raise SystemExit("Neo4j est injoignable : vérifier NEO4J_URI et que le service est démarré.")
    if args.reset:
        services.repository.reset()
    services.ensure_schema()
    if args.use_llm and not services.settings.llm_enabled:
        raise SystemExit("--use-llm demandé mais aucun fournisseur LLM n'est configuré (LLM_PROVIDER / LLM_API_KEY).")
    report = services.pipeline.sync_directory(args.dir, delete_missing=not args.no_delete, use_llm=args.use_llm)
    summary = {
        "run_id": report.run_id, "duration_seconds": report.duration_seconds, "files_seen": report.files_seen,
        **{k: report.count(k) for k in ("ingested", "updated", "unchanged", "duplicate", "quarantined", "rejected", "error")},
        "deleted": report.deleted_documents,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for r in report.results:
        if r.outcome not in ("ingested", "updated", "unchanged"):
            print(f"  - {r.file_name}: {r.outcome} — {r.message}")
    services.close()


if __name__ == "__main__":
    main()
