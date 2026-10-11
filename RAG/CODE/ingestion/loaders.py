"""Extraction du texte brut selon le format, avec bascule automatique vers l'OCR.

Sortie commune (`RawDocument`) : liste de pages de texte, indicateurs OCR et propriétés du
fichier (titre, auteur, sujet...) lues dans les métadonnées internes du PDF ou du DOCX.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ingestion.ocr import ocr_pdf_page

logger = logging.getLogger(__name__)


@dataclass
class RawDocument:
    pages: list[str]
    ocr_used: bool = False
    ocr_pages: int = 0
    ocr_confidence: float | None = None
    properties: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n\f\n".join(self.pages)


def load_pdf(path: Path, *, ocr_languages: str, ocr_dpi: int, ocr_min_page_chars: int) -> RawDocument:
    import pymupdf

    pages: list[str] = []
    confidences: list[float] = []
    ocr_pages = 0
    with pymupdf.open(path) as doc:
        meta = doc.metadata or {}
        for page in doc:
            text = page.get_text("text") or ""
            if len(text.strip()) < ocr_min_page_chars:
                # Page sans couche texte : document scanné -> OCR.
                result = ocr_pdf_page(page, dpi=ocr_dpi, languages=ocr_languages)
                text = result.text
                confidences.append(result.mean_confidence)
                ocr_pages += 1
            pages.append(text)
    props = {
        "title": (meta.get("title") or "").strip() or None,
        "author": (meta.get("author") or "").strip() or None,
        "subject": (meta.get("subject") or "").strip() or None,
    }
    return RawDocument(
        pages=pages,
        ocr_used=ocr_pages > 0,
        ocr_pages=ocr_pages,
        ocr_confidence=(sum(confidences) / len(confidences)) if confidences else None,
        properties=props,
    )


def load_docx(path: Path) -> RawDocument:
    from docx import Document

    document = Document(str(path))
    lines: list[str] = []
    # Les tableaux (ex. cartouche) sont lus en premier : ils précèdent le corps du texte.
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "tbl":
            for row in child.iter():
                if row.tag.rsplit("}", 1)[-1] == "tr":
                    cells = ["".join(t.text or "" for t in cell.iter() if t.tag.rsplit("}", 1)[-1] == "t")
                             for cell in row if cell.tag.rsplit("}", 1)[-1] == "tc"]
                    line = " | ".join(c.strip() for c in cells if c.strip())
                    if line:
                        lines.append(line)
        elif tag == "p":
            text = "".join(t.text or "" for t in child.iter() if t.tag.rsplit("}", 1)[-1] == "t")
            style = ""
            ppr = [e for e in child.iter() if e.tag.rsplit("}", 1)[-1] == "pStyle"]
            if ppr:
                style = next(iter(ppr[0].attrib.values()), "")
            if text.strip():
                if style.lower().startswith(("heading", "titre")) and not text.startswith("#"):
                    level = "".join(ch for ch in style if ch.isdigit()) or "1"
                    text = "#" * int(level) + " " + text
                elif style.lower().startswith(("listbullet", "listnumber", "listparagraph")):
                    text = "- " + text
                lines.append(text)
            else:
                lines.append("")
    core = document.core_properties
    props = {
        "title": core.title or None,
        "author": core.author or None,
        "subject": core.subject or None,
        "created": core.created.isoformat() if core.created else None,
    }
    return RawDocument(pages=["\n".join(lines)], properties=props)


def load_txt(path: Path) -> RawDocument:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    return RawDocument(pages=[text], properties={})


def load_document(path: Path, *, ocr_languages: str = "fra+eng", ocr_dpi: int = 300,
                  ocr_min_page_chars: int = 30) -> RawDocument:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return load_pdf(path, ocr_languages=ocr_languages, ocr_dpi=ocr_dpi, ocr_min_page_chars=ocr_min_page_chars)
    if ext == ".docx":
        return load_docx(path)
    if ext == ".txt":
        return load_txt(path)
    raise ValueError(f"Format non pris en charge : {ext}")
