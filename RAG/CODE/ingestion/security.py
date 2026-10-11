"""Contrôles de sécurité appliqués avant et pendant l'ingestion.

1. Validation des fichiers : extension autorisée, taille maximale, type réel vérifié par la
   signature binaire (« magic bytes »), PDF chiffré refusé, nombre de pages borné, archive
   DOCX contrôlée contre les bombes de décompression.
2. Détection d'injection de prompt : un document peut contenir des instructions destinées à
   détourner le LLM (injection indirecte, Greshake et al., 2023). Les motifs détectés placent
   le document en quarantaine : il est conservé pour revue humaine mais exclu du graphe et
   de la recherche.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class FileRejected(ValueError):
    """Fichier refusé (motif lisible par un humain dans le message)."""


@dataclass
class FileCheck:
    extension: str
    size_bytes: int


def validate_file(path: Path, *, max_mb: int, max_pdf_pages: int, max_docx_uncompressed_mb: int) -> FileCheck:
    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileRejected(f"extension non autorisée ({ext or 'aucune'})")
    size = path.stat().st_size
    if size == 0:
        raise FileRejected("fichier vide")
    if size > max_mb * 1024 * 1024:
        raise FileRejected(f"taille {size / 1e6:.1f} Mo supérieure à la limite de {max_mb} Mo")

    with path.open("rb") as handle:
        head = handle.read(8)

    if ext == ".pdf":
        if not head.startswith(b"%PDF-"):
            raise FileRejected("le contenu ne correspond pas à un PDF (signature absente)")
        import pymupdf

        try:
            with pymupdf.open(path) as doc:
                if doc.needs_pass or doc.is_encrypted:
                    raise FileRejected("PDF chiffré ou protégé par mot de passe")
                if doc.page_count > max_pdf_pages:
                    raise FileRejected(f"{doc.page_count} pages (limite : {max_pdf_pages})")
        except FileRejected:
            raise
        except Exception as exc:  # PDF corrompu
            raise FileRejected(f"PDF illisible ou corrompu ({type(exc).__name__})") from exc

    elif ext == ".docx":
        if not head.startswith(b"PK\x03\x04"):
            raise FileRejected("le contenu ne correspond pas à un DOCX (archive ZIP attendue)")
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                if "word/document.xml" not in names:
                    raise FileRejected("archive ZIP sans word/document.xml (pas un DOCX)")
                total = sum(info.file_size for info in archive.infolist())
                if total > max_docx_uncompressed_mb * 1024 * 1024:
                    raise FileRejected("taille décompressée excessive (bombe de décompression suspectée)")
                if any(name.startswith(("/", "..")) or "/../" in name for name in names):
                    raise FileRejected("chemins suspects dans l'archive")
        except zipfile.BadZipFile as exc:
            raise FileRejected("archive DOCX corrompue") from exc

    elif ext == ".txt":
        with path.open("rb") as handle:
            sample = handle.read(65536)
        if b"\x00" in sample:
            raise FileRejected("fichier texte contenant des octets nuls (binaire suspecté)")

    return FileCheck(extension=ext, size_bytes=size)


# --------------------------------------------------------------------------- injection
_INJECTION_PATTERNS = [
    (r"ignor\w*\s+(toutes\s+)?(les\s+)?(instructions|consignes)\s+(pr[ée]c[ée]dentes|ant[ée]rieures|ci-dessus)", "instruction de contournement"),
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", "instruction de contournement (anglais)"),
    (r"(note|message|instruction)s?\s+(pour|à)\s+l['’]?\s*(assistant|ia|intelligence artificielle|llm|chatbot)", "adresse directe à l'assistant"),
    (r"(r[ée]v[èe]le|affiche|divulgue)\w*\s+(le\s+)?(prompt|message)\s+syst[èe]me", "demande de divulgation du prompt système"),
    (r"(system\s+prompt|you\s+are\s+now|act\s+as)", "manipulation de rôle (anglais)"),
    (r"!\[[^\]]*\]\(\s*https?://", "image Markdown pointant vers un domaine externe (exfiltration)"),
    (r"(r[ée]ponds|r[ée]pondre)\s+d[ée]sormais", "consigne de réponse imposée"),
]
_COMPILED = [(re.compile(p, re.IGNORECASE), label) for p, label in _INJECTION_PATTERNS]


def detect_prompt_injection(text: str) -> list[str]:
    """Retourne la liste des motifs d'injection détectés (vide si aucun)."""
    found = []
    for pattern, label in _COMPILED:
        if pattern.search(text):
            found.append(label)
    return found
