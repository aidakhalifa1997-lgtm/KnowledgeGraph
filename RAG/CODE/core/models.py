"""Modèles de données échangés entre les étapes du pipeline (validés par Pydantic)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

DocumentStatus = Literal["active", "superseded", "duplicate", "quarantined", "rejected"]


class QualityIssue(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"]
    message: str


class DocumentRecord(BaseModel):
    """Document normalisé prêt à être écrit dans le graphe."""

    id: str
    file_name: str
    source_path: str
    format: str
    content_hash: str
    size_bytes: int
    title: str
    reference: str | None = None
    version: str | None = None
    doc_date: date | None = None
    doc_type: str = "document"
    department_name: str | None = None
    department_id: str | None = None
    author_name: str | None = None
    author_id: str | None = None
    classification: str = "Interne"
    diffusion: list[str] = Field(default_factory=lambda: ["ALL"])
    pages: int = 1
    ocr_used: bool = False
    ocr_confidence: float | None = None
    language: str = "fr"
    quality_score: float = 1.0
    issues: list[QualityIssue] = Field(default_factory=list)
    status: DocumentStatus = "active"
    duplicate_of: str | None = None
    supersedes: list[str] = Field(default_factory=list)
    describes: list[str] = Field(default_factory=list)
    text: str = ""


class ChunkRecord(BaseModel):
    id: str
    doc_id: str
    index: int
    text: str
    section: str = ""
    page: int | None = None
    char_start: int = 0
    char_end: int = 0
    embedding: list[float] | None = None


class Mention(BaseModel):
    """Occurrence d'une entité dans un passage."""

    surface: str
    start: int
    end: int
    entity_id: str | None
    entity_type: str | None
    method: Literal["exact", "alias", "context", "fuzzy", "ner", "llm"] = "alias"
    confidence: float = 1.0
    title_alias: bool = False  # forme « Directrice Conformité » : titre de fonction


class ExtractedRelation(BaseModel):
    subject_id: str
    relation: str
    object_id: str
    roles: list[str] = Field(default_factory=list)
    evidence: str
    chunk_id: str
    doc_id: str
    confidence: float
    extractor: Literal["rules", "llm", "rules+llm"]


class CandidateEntity(BaseModel):
    """Entité absente du référentiel, créée avec le statut `candidate` (revue humaine)."""

    id: str
    type: str
    name: str
    surface: str
    chunk_id: str
    doc_id: str
    possible_match: str | None = None
    match_score: float | None = None


class StageTiming(BaseModel):
    stage: str
    seconds: float


class DocumentIngestionResult(BaseModel):
    file_name: str
    doc_id: str | None = None
    outcome: Literal["ingested", "updated", "unchanged", "duplicate", "quarantined", "rejected", "error"]
    status: str | None = None
    message: str = ""
    chunks: int = 0
    mentions: int = 0
    relations: int = 0
    candidates: int = 0
    issues: list[QualityIssue] = Field(default_factory=list)
    timings: list[StageTiming] = Field(default_factory=list)


class IngestionReport(BaseModel):
    run_id: str
    started_at: str
    finished_at: str | None = None
    duration_seconds: float = 0.0
    files_seen: int = 0
    results: list[DocumentIngestionResult] = Field(default_factory=list)
    deleted_documents: list[str] = Field(default_factory=list)

    def count(self, outcome: str) -> int:
        return sum(1 for r in self.results if r.outcome == outcome)
