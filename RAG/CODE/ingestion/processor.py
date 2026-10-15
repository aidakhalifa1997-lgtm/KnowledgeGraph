"""Traitement complet d'un document, indépendant de la base de données.

Fichier -> validation -> extraction du texte (OCR si nécessaire) -> nettoyage -> métadonnées
-> contrôle qualité -> détection d'injection -> découpage -> reconnaissance d'entités ->
extraction de relations (règles, puis LLM si configuré) -> signature MinHash.

Le résultat (`ProcessedDocument`) est ensuite écrit dans Neo4j par `ingestion/pipeline.py`.
Cette séparation permet de tester et d'évaluer l'extraction sans base de données.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from core.models import (
    CandidateEntity,
    ChunkRecord,
    DocumentRecord,
    ExtractedRelation,
    Mention,
    QualityIssue,
    StageTiming,
)
from core.settings import Settings
from core.text import normalize_key, slugify
from extraction.linker import EntityLinker
from extraction.llm_extractor import LLMExtractor
from extraction.merge import merge_relations
from extraction.referential import Referential
from extraction.rules import DocContext, RuleExtractor
from ingestion.chunking import chunk_document
from ingestion.cleaning import finalize_pages, prepare_pages
from ingestion.dedup import minhash_signature, sha256_file
from ingestion.loaders import load_document
from ingestion.metadata import extract_metadata
from ingestion.quality import assess_quality
from ingestion.security import detect_prompt_injection, validate_file

logger = logging.getLogger(__name__)


@dataclass
class ProcessedDocument:
    record: DocumentRecord
    chunks: list[ChunkRecord] = field(default_factory=list)
    mentions: dict[str, list[Mention]] = field(default_factory=dict)
    relations: list[ExtractedRelation] = field(default_factory=list)
    candidates: list[CandidateEntity] = field(default_factory=list)
    injection_findings: list[str] = field(default_factory=list)
    minhash: list[int] = field(default_factory=list)
    timings: list[StageTiming] = field(default_factory=list)
    llm_relations: int = 0


def document_id_for(file_name: str) -> str:
    return "doc-" + hashlib.sha1(file_name.lower().encode("utf-8")).hexdigest()[:12]  # noqa: S324 (identifiant, pas sécurité)


class DocumentProcessor:
    def __init__(self, settings: Settings, referential: Referential, linker: EntityLinker,
                 rule_extractor: RuleExtractor, llm_extractor: LLMExtractor | None = None) -> None:
        self.settings = settings
        self.ref = referential
        self.linker = linker
        self.rules = rule_extractor
        self.llm = llm_extractor

    # ------------------------------------------------------------------
    def describe(self, reference: str | None, title: str) -> list[str]:
        """Entité(s) décrite(s) par le document : procédure (code de référence), projet (code
        projet du portefeuille) ou projet/système cité dans le titre."""
        described: list[str] = []
        if reference:
            ref_key = normalize_key(reference)
            for proc in self.ref.by_type("Procedure"):
                if any(normalize_key(a) == ref_key for a in proc.aliases):
                    described.append(proc.id)
            for segment in reference.upper().split("-"):
                project = self.ref.project_by_code(segment)
                if project and project.id not in described:
                    described.append(project.id)
        if not described:
            for m in self.linker.find_mentions(title):
                if m.entity_id and m.entity_type in ("Project", "System", "Procedure") and m.entity_id not in described:
                    described.append(m.entity_id)
                    break
        return described

    def process(self, path: Path, use_llm: bool = False) -> ProcessedDocument:
        timings: list[StageTiming] = []

        def timed(stage: str, started: float) -> None:
            timings.append(StageTiming(stage=stage, seconds=round(time.perf_counter() - started, 4)))

        t = time.perf_counter()
        check = validate_file(path, max_mb=self.settings.max_upload_mb, max_pdf_pages=self.settings.max_pdf_pages,
                              max_docx_uncompressed_mb=self.settings.max_docx_uncompressed_mb)
        data = path.read_bytes()
        content_hash = sha256_file(data)
        timed("validation", t)

        t = time.perf_counter()
        raw = load_document(path, ocr_languages=self.settings.ocr_languages, ocr_dpi=self.settings.ocr_dpi,
                            ocr_min_page_chars=self.settings.ocr_min_page_chars)
        timed("extraction_texte" + ("_ocr" if raw.ocr_used else ""), t)

        t = time.perf_counter()
        pages = prepare_pages(raw.pages)
        meta, first_body = extract_metadata(pages[0] if pages else "", raw.properties, path.name)
        if pages:
            pages[0] = first_body
        pages = finalize_pages(pages, is_pdf=check.extension == ".pdf")
        text = "\n\n".join(p for p in pages if p.strip())
        timed("nettoyage_metadonnees", t)

        author = self.linker.resolver.resolve(meta.author_name, "Person") if meta.author_name else None
        department = self.linker.resolver.resolve(meta.department_name, "Department") if meta.department_name else None
        quality, issues, language = assess_quality(text, ocr_confidence=raw.ocr_confidence, reference=meta.reference,
                                                   doc_date=meta.doc_date, author=meta.author_name,
                                                   department=meta.department_name,
                                                   diffusion_declared="diffusion" in meta.found_in_cartouche)
        injection = detect_prompt_injection(text)
        status = "active"
        if any(i.severity == "error" for i in issues):
            status = "rejected"
        elif injection:
            status = "quarantined"
            issues.append(QualityIssue(code="prompt_injection", severity="error",
                                       message="instructions destinées à un assistant IA détectées : " + ", ".join(injection)))
        doc_id = document_id_for(path.name)
        described = self.describe(meta.reference, meta.title or path.name)
        record = DocumentRecord(
            id=doc_id, file_name=path.name, source_path=str(path), format=check.extension.lstrip("."),
            content_hash=content_hash, size_bytes=check.size_bytes, title=meta.title or path.name,
            reference=meta.reference, version=meta.version, doc_date=meta.doc_date, doc_type=meta.doc_type,
            department_name=meta.department_name, department_id=department.entity_id if department else None,
            author_name=meta.author_name, author_id=author.entity_id if author else None,
            classification=meta.classification, diffusion=meta.diffusion, pages=len(raw.pages),
            ocr_used=raw.ocr_used, ocr_confidence=round(raw.ocr_confidence, 1) if raw.ocr_confidence else None,
            language=language, quality_score=quality, issues=issues, status=status, describes=described, text=text,
        )
        result = ProcessedDocument(record=record, injection_findings=injection, timings=timings)
        if status in ("rejected", "quarantined"):
            return result

        t = time.perf_counter()
        for chunk in chunk_document(pages):
            result.chunks.append(ChunkRecord(id=f"{doc_id}#c{chunk.index:03d}", doc_id=doc_id, index=chunk.index,
                                             text=chunk.text, section=chunk.section, page=chunk.page,
                                             char_start=chunk.char_start, char_end=chunk.char_end))
        timed("decoupage", t)

        t = time.perf_counter()
        ctx = DocContext(doc_id=doc_id, described_ids=described,
                         described_types={i: self.ref.entities[i].type for i in described if i in self.ref.entities})
        rule_relations: list[ExtractedRelation] = []
        for chunk in result.chunks:
            mentions = self.linker.find_mentions(chunk.text)
            result.mentions[chunk.id] = mentions
            rule_relations.extend(self.rules.extract(chunk.id, chunk.text, mentions, ctx))
            for m in mentions:
                if m.entity_id is None and m.entity_type == "Person" and m.method == "ner":
                    resolution = self.linker.resolver.resolve(m.surface, "Person")
                    result.candidates.append(CandidateEntity(
                        id=f"per:cand-{slugify(m.surface)}", type="Person", name=m.surface.strip(), surface=m.surface,
                        chunk_id=chunk.id, doc_id=doc_id, possible_match=resolution.possible_match,
                        match_score=resolution.score or None))
        timed("entites_relations_regles", t)

        llm_relations: list[ExtractedRelation] = []
        if use_llm and self.llm is not None:
            t = time.perf_counter()
            for chunk in result.chunks:
                llm_relations.extend(self.llm.extract(chunk.id, doc_id, chunk.text, result.mentions[chunk.id], ctx))
            timed("relations_llm", t)
        result.llm_relations = len(llm_relations)
        result.relations = merge_relations(rule_relations + llm_relations)
        result.minhash = minhash_signature(text)
        return result
