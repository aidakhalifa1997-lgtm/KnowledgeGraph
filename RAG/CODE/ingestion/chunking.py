"""Découpage des documents en passages (« chunks »).

Stratégie structurelle : on respecte les sections (titres) et les paragraphes plutôt que de
couper tous les N caractères. Un passage :
- appartient à une seule section (son titre est conservé dans `section`) ;
- vise environ `target_chars` caractères (≈ 150 à 200 mots), sans dépasser `max_chars` ;
- reprend la dernière phrase du passage précédent de la même section (chevauchement
  minimal) pour ne pas couper un raisonnement en deux.

Le texte indexé pour la recherche est enrichi du titre du document et de la section
(« en-tête contextuel ») : un passage « Le délai est de 48 heures » devient retrouvable par
une question qui mentionne la procédure concernée.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.text import split_sentences

_HEADING = re.compile(r"^(#{1,6})\s+(.+)$|^(\d+(?:\.\d+)*\.?)\s+([A-ZÉÈÀÂÎÔÛÇ][^.;:]{0,70})$")


@dataclass
class Paragraph:
    text: str
    section: str
    page: int
    start: int


@dataclass
class Chunk:
    index: int
    text: str
    section: str
    page: int
    char_start: int
    char_end: int


def _is_heading(line: str) -> str | None:
    m = _HEADING.match(line.strip())
    if not m:
        stripped = line.strip()
        if 6 <= len(stripped) <= 90 and stripped.isupper() and not stripped.endswith("."):
            return stripped.title() if len(stripped) > 60 else stripped
        # Titre court sans numérotation (fréquent dans les PDF) : 1 à 5 mots, majuscule
        # initiale, sans ponctuation finale ni « : ».
        words = stripped.split()
        if (1 <= len(words) <= 5 and len(stripped) <= 45 and stripped[:1].isupper()
                and not stripped.endswith((".", ":", ";", ",")) and ":" not in stripped
                and not stripped.startswith(("-", "|"))):
            return stripped
        return None
    if m.group(1):
        return m.group(2).strip()
    return f"{m.group(3)} {m.group(4)}".strip()


def paragraphs_from_pages(pages: list[str]) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    section = ""
    offset = 0
    for page_no, page in enumerate(pages, start=1):
        for line in page.split("\n"):
            stripped = line.strip()
            if not stripped:
                offset += len(line) + 1
                continue
            heading = _is_heading(stripped)
            if heading:
                section = heading
            else:
                paragraphs.append(Paragraph(text=stripped, section=section, page=page_no, start=offset))
            offset += len(line) + 1
    return paragraphs


def chunk_paragraphs(paragraphs: list[Paragraph], target_chars: int = 900, max_chars: int = 1400) -> list[Chunk]:
    chunks: list[Chunk] = []
    buffer: list[Paragraph] = []

    def flush() -> None:
        if not buffer:
            return
        text = "\n".join(p.text for p in buffer)
        chunks.append(Chunk(index=len(chunks), text=text, section=buffer[0].section, page=buffer[0].page,
                            char_start=buffer[0].start, char_end=buffer[-1].start + len(buffer[-1].text)))

    for para in paragraphs:
        pieces = [para]
        if len(para.text) > max_chars:  # paragraphe trop long : découpe par phrases
            pieces, current = [], ""
            for sent in split_sentences(para.text):
                if current and len(current) + len(sent) + 1 > target_chars:
                    pieces.append(Paragraph(current, para.section, para.page, para.start))
                    current = sent
                else:
                    current = f"{current} {sent}".strip()
            if current:
                pieces.append(Paragraph(current, para.section, para.page, para.start))
        for piece in pieces:
            current_len = sum(len(p.text) + 1 for p in buffer)
            new_section = buffer and piece.section != buffer[0].section
            if buffer and (new_section or current_len + len(piece.text) > target_chars):
                previous_last = buffer[-1]
                flush()
                buffer = []
                if not new_section:
                    # Chevauchement : dernière phrase du passage précédent.
                    last_sentence = split_sentences(previous_last.text)[-1:] or []
                    if last_sentence and len(last_sentence[0]) < 300:
                        buffer.append(Paragraph(last_sentence[0], previous_last.section, previous_last.page,
                                                previous_last.start))
            buffer.append(piece)
    flush()
    return chunks


def chunk_document(pages: list[str], target_chars: int = 900, max_chars: int = 1400) -> list[Chunk]:
    return chunk_paragraphs(paragraphs_from_pages(pages), target_chars=target_chars, max_chars=max_chars)


def contextual_text(title: str, section: str, text: str) -> str:
    """Texte enrichi utilisé pour l'indexation lexicale et vectorielle."""
    parts = [title.strip()]
    if section and section.lower() not in title.lower():
        parts.append(section.strip())
    parts.append(text.strip())
    return "\n".join(parts)
