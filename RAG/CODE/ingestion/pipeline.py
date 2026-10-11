"""Pipeline d'ingestion : du répertoire source au Knowledge Graph.

Pour chaque fichier :
1. empreinte SHA-256 : un fichier inchangé depuis la dernière ingestion est ignoré ;
2. doublon exact (même empreinte qu'un autre document) : tracé comme `duplicate` ;
3. traitement complet (`DocumentProcessor`) ;
4. document rejeté (qualité) ou en quarantaine (injection) : tracé sans contenu indexé ;
5. quasi-doublon (MinHash) d'un document existant de même référence et version : `duplicate` ;
6. calcul des embeddings des passages et écriture transactionnelle dans Neo4j.

Choix du document canonique entre deux doublons : celui dont le nom ou le contenu ne porte
pas de marqueur de brouillon/copie (« copie », « brouillon », « travail »...) ; à défaut, le
premier ingéré.

En mode synchronisation, un document présent dans le graphe mais absent du répertoire source
est supprimé (ainsi que les relations qu'il était seul à justifier). En fin de passe :
versions (SUPERSEDES), relations dérivées (COVERS, BELONGS_TO), similarités, nettoyage des
entités orphelines et journal d'exécution (nœud IngestionRun).
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from core.models import DocumentIngestionResult, IngestionReport, QualityIssue, StageTiming
from core.settings import Settings
from ingestion.chunking import contextual_text
from ingestion.dedup import estimated_jaccard, sha256_file
from ingestion.processor import DocumentProcessor, document_id_for
from ingestion.security import ALLOWED_EXTENSIONS, FileRejected
from knowledge_graph.repository import GraphRepository
from retrieval.embeddings import Embedder

logger = logging.getLogger(__name__)

NEAR_DUPLICATE_THRESHOLD = 0.80
_DRAFT = re.compile(r"(copie|copy|brouillon|draft|travail|temporaire|tmp|old)", re.IGNORECASE)


def has_draft_marker(file_name: str, text: str = "") -> bool:
    return bool(_DRAFT.search(file_name) or _DRAFT.search(text[:300]))


class IngestionPipeline:
    def __init__(self, settings: Settings, repo: GraphRepository, processor: DocumentProcessor,
                 embedder: Embedder) -> None:
        self.settings = settings
        self.repo = repo
        self.processor = processor
        self.embedder = embedder

    # ------------------------------------------------------------------
    def ingest_file(self, path: Path, *, use_llm: bool = False) -> DocumentIngestionResult:
        doc_id = document_id_for(path.name)
        try:
            data = path.read_bytes()
        except OSError as exc:
            return DocumentIngestionResult(file_name=path.name, doc_id=doc_id, outcome="error", message=str(exc))
        content_hash = sha256_file(data)
        state = self.repo.get_document_state(doc_id)
        if state and state["hash"] == content_hash:
            return DocumentIngestionResult(file_name=path.name, doc_id=doc_id, outcome="unchanged",
                                           status=state["status"])
        try:
            processed = self.processor.process(path, use_llm=use_llm)
        except FileRejected as exc:
            logger.warning("Fichier refusé", extra={"file": path.name, "reason": str(exc)})
            return DocumentIngestionResult(file_name=path.name, doc_id=doc_id, outcome="rejected", status="rejected",
                                           message=str(exc))
        except Exception as exc:  # erreur inattendue : tracée, l'ingestion des autres fichiers continue
            logger.exception("Erreur de traitement", extra={"file": path.name})
            return DocumentIngestionResult(file_name=path.name, doc_id=doc_id, outcome="error",
                                           message=f"{type(exc).__name__}: {exc}")

        record = processed.record
        draft = has_draft_marker(path.name, record.text)
        result = DocumentIngestionResult(file_name=path.name, doc_id=doc_id, outcome="ingested", status=record.status,
                                         issues=record.issues, timings=processed.timings)

        # Doublon exact d'un autre document.
        other = self.repo.find_by_hash(content_hash, exclude_id=doc_id)
        if other:
            return self._handle_duplicate(processed, other["id"], other["file_name"], draft, result, exact=True)

        if record.status in ("rejected", "quarantined"):
            self.repo.write_shell(record, draft_marker=draft)
            result.outcome = record.status
            result.message = "; ".join(i.message for i in record.issues if i.severity == "error")
            return result

        # Quasi-doublon : même référence et même version, contenu presque identique.
        for sig in self.repo.signatures():
            if sig["id"] == doc_id or not sig["minhash"]:
                continue
            similarity = estimated_jaccard(processed.minhash, sig["minhash"])
            if similarity >= NEAR_DUPLICATE_THRESHOLD and sig["reference"] == record.reference \
                    and sig["version"] == record.version:
                record.issues.append(QualityIssue(code="near_duplicate", severity="warning",
                                                  message=f"quasi-doublon de {sig['file_name']} (Jaccard ≈ {similarity:.2f})"))
                return self._handle_duplicate(processed, sig["id"], sig["file_name"], draft, result, exact=False,
                                              other_draft=bool(sig.get("draft_marker")))
            if similarity >= NEAR_DUPLICATE_THRESHOLD:
                record.issues.append(QualityIssue(code="similar_document", severity="info",
                                                  message=f"contenu très proche de {sig['file_name']} (Jaccard ≈ {similarity:.2f})"))

        self._write(processed, draft)
        result.outcome = "updated" if state else "ingested"
        result.status = "active"
        result.chunks = len(processed.chunks)
        result.mentions = sum(len(m) for m in processed.mentions.values())
        result.relations = len(processed.relations)
        result.candidates = len(processed.candidates)
        return result

    def _write(self, processed, draft: bool) -> None:
        texts = [contextual_text(processed.record.title, c.section, c.text) for c in processed.chunks]
        t = time.perf_counter()
        embeddings = self.embedder.embed(texts)
        processed.timings.append(StageTiming(stage="embeddings", seconds=round(time.perf_counter() - t, 4)))
        t = time.perf_counter()
        self.repo.write_document(processed, embeddings, draft_marker=draft)
        processed.timings.append(StageTiming(stage="ecriture_neo4j", seconds=round(time.perf_counter() - t, 4)))

    def _handle_duplicate(self, processed, other_id: str, other_name: str, draft: bool, result, *, exact: bool,
                          other_draft: bool | None = None) -> DocumentIngestionResult:
        record = processed.record
        if other_draft is None:
            other_draft = has_draft_marker(other_name)
        kind = "doublon exact" if exact else "quasi-doublon"
        if other_draft and not draft and record.status == "active":
            # Le document existant est un brouillon/une copie : le nouveau devient canonique.
            self._write(processed, draft)
            self.repo.mark_duplicate(other_id, record.id)
            result.outcome = "ingested"
            result.status = "active"
            result.message = f"{other_name} reclassé comme {kind} de ce document"
            return result
        record.status = "duplicate"
        self.repo.write_shell(record, draft_marker=draft, duplicate_of=other_id)
        result.outcome = "duplicate"
        result.status = "duplicate"
        result.message = f"{kind} de {other_name}"
        return result

    # ------------------------------------------------------------------
    def finalize(self) -> None:
        self.repo.update_versions()
        self.repo.derive_taxonomy_links()
        self.repo.derive_covers()
        self.repo.compute_similar_to()
        self.repo.cleanup_orphans()

    def sync_directory(self, directory: str | Path | None = None, *, delete_missing: bool = True,
                       use_llm: bool = False) -> IngestionReport:
        directory = Path(directory or self.settings.documents_dir).resolve()
        started = time.perf_counter()
        report = IngestionReport(run_id=f"run-{uuid.uuid4().hex[:10]}",
                                 started_at=datetime.now(UTC).isoformat(timespec="seconds"))
        files = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS)
        report.files_seen = len(files)
        for path in files:
            result = self.ingest_file(path, use_llm=use_llm)
            report.results.append(result)
            logger.info("Document traité", extra={"file": path.name, "outcome": result.outcome,
                                                  "chunks": result.chunks, "relations": result.relations})
        if delete_missing:
            present = {document_id_for(p.name) for p in files}
            for doc in self.repo.documents_from_source(str(directory)):
                if doc["id"] not in present:
                    self.repo.delete_document(doc["id"])
                    report.deleted_documents.append(doc["file_name"])
        self.finalize()
        report.finished_at = datetime.now(UTC).isoformat(timespec="seconds")
        report.duration_seconds = round(time.perf_counter() - started, 2)
        self.repo.record_run(report)
        return report

    def delete(self, doc_id: str) -> bool:
        deleted = self.repo.delete_document(doc_id)
        if deleted:
            self.finalize()
        return deleted
