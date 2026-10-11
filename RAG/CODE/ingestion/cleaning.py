"""Nettoyage et normalisation du texte extrait.

Problèmes traités (fréquents dans les PDF d'entreprise) :
- caractères Unicode hétérogènes (apostrophes typographiques, ligatures, tirets) ;
- en-têtes et pieds de page répétés à chaque page (« Page 3 », référence du document) ;
- césures de fin de ligne (« connais-\\nsance ») ;
- retours à la ligne « visuels » du PDF au milieu des phrases ;
- espaces et lignes vides superflus.

Le texte est conservé page par page pour permettre de citer la page source.
"""

from __future__ import annotations

import re
from collections import Counter

from core.text import normalize_unicode

_PAGE_NUMBER = re.compile(r"^\s*(page\s*)?\d+\s*(/|sur)?\s*\d*\s*$", re.IGNORECASE)
# Pied de page des gabarits documentaires de la banque : « PRC-KYC-001 - v1.0 - Interne ».
_TEMPLATE_FOOTER = re.compile(r"^\S+\s+-\s+v\d+(\.\d+)*\s+-\s+(Interne|Confidentiel|Restreint|Public)\s*$", re.IGNORECASE)
_HEADING = re.compile(r"^(#{1,6}\s+.+|\d+(\.\d+)*\.?\s+[A-ZÉÈÀÂÎÔÛÇ«\"].{0,80}|[A-ZÉÈÀÂÎÔÛÇ0-9 ,'’()/-]{6,90})$")
_BULLET = re.compile(r"^\s*([-•*▪●◦]|\d+[.)])\s+")


_FIELD_LINE = re.compile(r"^[\wÀ-ÿ'’ ()-]{2,40}\s:\s?\S")


def _is_structural(line: str) -> bool:
    """Titre, puce ou ligne « Clé : valeur » : ne doit jamais être fusionnée avec ses voisines."""
    stripped = line.strip()
    return bool(_HEADING.match(stripped) or _BULLET.match(stripped) or _FIELD_LINE.match(stripped))


def remove_repeated_lines(pages: list[str], min_ratio: float = 0.6) -> list[str]:
    """Supprime les lignes présentes sur au moins `min_ratio` des pages (en-têtes, pieds)."""
    if len(pages) < 2:
        return pages
    counter: Counter[str] = Counter()
    for page in pages:
        counter.update({line.strip() for line in page.splitlines() if line.strip()})
    threshold = max(2, int(len(pages) * min_ratio))
    repeated = {line for line, n in counter.items() if n >= threshold and len(line) < 120}
    return ["\n".join(line for line in page.splitlines() if line.strip() not in repeated) for page in pages]


def clean_page(text: str, join_wrapped_lines: bool) -> str:
    text = normalize_unicode(text).replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = text.replace(" ", " ").replace(" ", " ")
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if _PAGE_NUMBER.match(stripped) and stripped:
            continue
        if _TEMPLATE_FOOTER.match(stripped):
            continue
        lines.append(re.sub(r"\s{2,}", " ", stripped))

    # Césures : « connais- » + « sance » -> « connaissance » (minuscule en début de ligne suivante).
    merged: list[str] = []
    for line in lines:
        if merged and merged[-1].endswith("-") and line[:1].islower() and len(merged[-1]) > 1 and merged[-1][-2].isalpha():
            merged[-1] = merged[-1][:-1] + line
        else:
            merged.append(line)

    # Puce isolée sur sa ligne (fréquent dans les PDF) : rattachée à la ligne suivante.
    with_bullets: list[str] = []
    pending_bullet = False
    for line in merged:
        if line in {"•", "-", "▪", "●", "◦", "*"}:
            pending_bullet = True
            continue
        if pending_bullet and line:
            line = f"- {line}"
            pending_bullet = False
        with_bullets.append(line)
    merged = with_bullets

    if join_wrapped_lines:
        joined: list[str] = []
        for line in merged:
            previous = joined[-1] if joined else ""
            if (
                previous
                and line
                and not previous.endswith((".", ":", ";", "!", "?"))
                and not _is_structural(line)  # une nouvelle puce, un titre ou un champ commence une ligne
                and not _HEADING.match(previous.strip())  # un titre n'est jamais prolongé
                and (line[:1].islower() or len(previous) > 55)
            ):
                joined[-1] = f"{previous} {line}"
            else:
                joined.append(line)
        merged = joined

    text = "\n".join(merged)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def prepare_pages(pages: list[str]) -> list[str]:
    """Première passe sans fusion de lignes : Unicode, en-têtes/pieds répétés, numéros de page.
    Les métadonnées (cartouche) sont lues sur ce texte, avant toute fusion."""
    pages = remove_repeated_lines([normalize_unicode(p) for p in pages])
    return [clean_page(p, join_wrapped_lines=False) for p in pages]


def finalize_pages(pages: list[str], *, is_pdf: bool) -> list[str]:
    """Seconde passe : césures et retours à la ligne visuels (PDF uniquement)."""
    return [clean_page(p, join_wrapped_lines=is_pdf) for p in pages]


def clean_pages(pages: list[str], *, is_pdf: bool) -> list[str]:
    return finalize_pages(prepare_pages(pages), is_pdf=is_pdf)
