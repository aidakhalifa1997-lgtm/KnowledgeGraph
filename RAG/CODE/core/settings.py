"""Configuration centralisée de la plateforme.

Toutes les valeurs proviennent de variables d'environnement (ou d'un fichier `.env` non
versionné). Aucune valeur secrète n'a de valeur par défaut réaliste : la clé LLM est vide
par défaut et le mode `offline` est utilisé tant qu'aucun fournisseur n'est configuré.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CODE_DIR = Path(__file__).resolve().parents[1]
RAG_DIR = CODE_DIR.parent
DATA_DIR = RAG_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(RAG_DIR / ".env"), str(CODE_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Neo4j ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("")
    neo4j_database: str = "neo4j"

    # --- LLM ---
    llm_provider: Literal["offline", "openai_compatible", "anthropic"] = "offline"
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 60.0
    llm_max_tokens: int = 1200
    llm_temperature: float = 0.0
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    llm_anthropic_fallbacks: bool = True
    llm_extraction_enabled: bool = False

    # --- Embeddings ---
    embedding_provider: Literal["spacy", "wordllama"] = "spacy"

    # --- API ---
    app_secret_key: SecretStr = SecretStr("")
    token_ttl_minutes: int = 480
    users_file: str = "config/users.example.yaml"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    ask_rate_limit_per_minute: int = 30

    # --- Ingestion ---
    documents_dir: str = str(DATA_DIR / "sample_documents")
    uploads_dir: str = str(DATA_DIR / "uploads")
    referentials_file: str = str(DATA_DIR / "synthetic_data" / "referentials" / "referentials.yaml")
    max_upload_mb: int = 20
    max_pdf_pages: int = 200
    max_docx_uncompressed_mb: int = 100
    ocr_languages: str = "fra+eng"
    ocr_dpi: int = 300
    ocr_min_page_chars: int = 30

    # --- Récupération / génération ---
    retrieval_top_k: int = 8
    candidate_pool: int = 40
    rrf_k: int = 60
    graph_max_hops: int = 2
    context_char_budget: int = 6000
    sufficiency_threshold: float = 0.55

    # --- Divers ---
    log_level: str = "INFO"
    reference_date: date = Field(default=date(2026, 10, 1))

    @field_validator("documents_dir", "uploads_dir", "referentials_file", "users_file")
    @classmethod
    def _resolve_relative(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            path = (CODE_DIR / path).resolve()
        return str(path)

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "offline" and bool(self.llm_api_key.get_secret_value())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
