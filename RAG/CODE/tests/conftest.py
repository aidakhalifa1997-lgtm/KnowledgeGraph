"""Fixtures partagées.

Tests unitaires : aucune dépendance externe (ni Neo4j, ni réseau, ni clé LLM).
Tests d'intégration (marqueur `integration`) : nécessitent une instance Neo4j DÉDIÉE aux tests,
désignée par NEO4J_TEST_URI / NEO4J_TEST_PASSWORD. Cette base est entièrement vidée : ne
jamais la faire pointer vers une base contenant des données utiles.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("APP_SECRET_KEY", "secret-de-test-0123456789-abcdefghijklmnopqrstuv")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ["LLM_PROVIDER"] = "offline"

from core.settings import CODE_DIR, DATA_DIR, Settings  # noqa: E402
from extraction.linker import EntityLinker  # noqa: E402
from extraction.referential import load_referential  # noqa: E402
from extraction.rules import RuleExtractor  # noqa: E402

SAMPLE_DIR = DATA_DIR / "sample_documents"
REFERENTIALS = DATA_DIR / "synthetic_data" / "referentials" / "referentials.yaml"


@pytest.fixture(scope="session")
def referential():
    return load_referential(REFERENTIALS)


@pytest.fixture(scope="session")
def linker(referential):
    return EntityLinker(referential, use_ner=False)


@pytest.fixture(scope="session")
def rule_extractor(referential):
    return RuleExtractor(referential, CODE_DIR / "config" / "extraction_rules.yaml")


@pytest.fixture(scope="session")
def sample_dir() -> Path:
    return SAMPLE_DIR


# ------------------------------------------------------------------ intégration Neo4j
def _test_settings(**overrides) -> Settings:
    uri = os.environ.get("NEO4J_TEST_URI")
    if not uri:
        pytest.skip("NEO4J_TEST_URI non défini : tests d'intégration ignorés")
    values = {"neo4j_uri": uri, "neo4j_password": os.environ.get("NEO4J_TEST_PASSWORD", "test-password-123"),
              "llm_provider": "offline", "app_secret_key": os.environ["APP_SECRET_KEY"]}
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(scope="session")
def integration_services(tmp_path_factory):
    """Services branchés sur la base de test, alimentée avec le corpus complet de démonstration."""
    from services import build_services

    docs = tmp_path_factory.mktemp("corpus")
    for f in SAMPLE_DIR.iterdir():
        if f.is_file():
            shutil.copy(f, docs / f.name)
    uploads = tmp_path_factory.mktemp("uploads")
    services = build_services(_test_settings(documents_dir=str(docs), uploads_dir=str(uploads)))
    if not services.client.ping():
        pytest.skip("Neo4j de test injoignable")
    services.repository.reset()
    services.ensure_schema()
    report = services.pipeline.sync_directory(docs)
    services.refresh_after_ingestion()
    services.ingestion_report = report
    services.corpus_dir = docs
    yield services
    services.close()
