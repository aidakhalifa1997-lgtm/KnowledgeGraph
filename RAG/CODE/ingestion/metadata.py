"""Extraction des métadonnées documentaires.

Sources, par ordre de priorité :
1. le cartouche du document (bloc d'en-tête normalisé des gabarits de la banque) ;
2. les propriétés internes du fichier (métadonnées PDF, propriétés DOCX) ;
3. le nom du fichier (référence, version) ;
4. le contenu (premier titre, date écrite en toutes lettres).

Le cartouche est retiré du corps du texte après lecture : il décrit le document mais ne
constitue pas une connaissance métier, et sa présence fausserait l'extraction de relations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

_FIELDS = {
    "reference": re.compile(r"^R[ée]f[ée]rence\s*:\s*(.+)$", re.IGNORECASE),
    "version": re.compile(r"^Version\s*:\s*(.+)$", re.IGNORECASE),
    "date": re.compile(r"^Date\s*:\s*(.+)$", re.IGNORECASE),
    "department": re.compile(r"^Direction propri[ée]taire\s*:\s*(.+)$", re.IGNORECASE),
    "author": re.compile(r"^R[ée]dacteur(?:\s*\(trice\))?\s*:\s*(.+)$", re.IGNORECASE),
    "classification": re.compile(r"^Classification\s*:\s*(.+)$", re.IGNORECASE),
    "diffusion": re.compile(r"^Diffusion\s*:\s*(.+)$", re.IGNORECASE),
}
_BANNER = re.compile(r"^ORIZIA BANQUE\b.*$", re.IGNORECASE)
_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
_CLASSIFICATIONS = {"public": "Public", "interne": "Interne", "confidentiel": "Confidentiel", "restreint": "Restreint"}

# Préfixe de référence -> type de document (convention de nommage du référentiel documentaire).
_DOC_TYPES = [
    (r"^PRC-", "procedure"), (r"^PRJ-.*-CH$", "charte_projet"), (r"^PRJ-.*-FP$", "fiche_projet"),
    (r"^PRJ-.*-(COPIL|REX)", "rapport"), (r"^CR-", "compte_rendu"), (r"^NO-", "note_organisation"),
    (r"^NS-", "note_de_service"), (r"^ARCH-", "note_technique"), (r"^CARTO-", "cartographie"),
    (r"^GU-", "guide"), (r"^AUD-", "rapport_audit"), (r"^RH-COMP", "referentiel_rh"), (r"^RH-FORM", "plan"),
    (r"^PM-", "rapport"), (r"^MEMO", "memo"),
]
_TITLE_TYPES = [
    ("procédure", "procedure"), ("charte", "charte_projet"), ("compte rendu", "compte_rendu"),
    ("note d'organisation", "note_organisation"), ("note de service", "note_de_service"), ("guide", "guide"),
    ("rapport d'audit", "rapport_audit"), ("rapport", "rapport"), ("fiche projet", "fiche_projet"),
]


@dataclass
class ParsedMetadata:
    title: str | None = None
    reference: str | None = None
    version: str | None = None
    doc_date: date | None = None
    department_name: str | None = None
    author_name: str | None = None
    classification: str = "Interne"
    diffusion: list[str] = field(default_factory=lambda: ["ALL"])
    doc_type: str = "document"
    found_in_cartouche: list[str] = field(default_factory=list)


def parse_date(value: str) -> date | None:
    value = value.strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if m:
        day, month, year = map(int, m.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        try:
            return date(*map(int, m.groups()))
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})(?:er)?\s+([a-zéû]+)\s+(\d{4})", value.lower())
    if m and m.group(2) in _MONTHS:
        try:
            return date(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    return None


def parse_diffusion(value: str) -> list[str]:
    low = value.lower()
    if "tous" in low or "public" in low or "général" in low:
        return ["ALL"]
    raw = value.split(":", 1)[-1]
    groups = [g.strip().upper() for g in re.split(r"[,;/]", raw) if g.strip()]
    return groups or ["ALL"]


def infer_doc_type(reference: str | None, title: str | None) -> str:
    if reference:
        for pattern, doc_type in _DOC_TYPES:
            if re.search(pattern, reference, re.IGNORECASE):
                return doc_type
    if title:
        low = title.lower()
        for keyword, doc_type in _TITLE_TYPES:
            if keyword in low:
                return doc_type
    return "document"


def extract_metadata(text: str, properties: dict, file_name: str) -> tuple[ParsedMetadata, str]:
    """Retourne les métadonnées et le texte débarrassé du cartouche."""
    meta = ParsedMetadata()
    body_lines: list[str] = []
    # Automate à trois états : avant le cartouche -> dans le cartouche -> corps du texte.
    # Le cartouche est un bloc contigu situé dans les 15 premières lignes ; dès qu'une ligne
    # de contenu le suit, la lecture s'arrête (une ligne « Rédacteur : ... » du corps n'est
    # donc pas confondue avec une métadonnée).
    state = "before"
    for idx, line in enumerate(text.split("\n")):
        stripped = line.strip().strip("|").strip()
        if state == "before" and idx > 15:
            state = "after"
        if state == "after":
            body_lines.append(line)
            continue
        if _BANNER.match(stripped) or re.match(r"^=+$", stripped):
            state = "inside"
            continue
        field = next(((key, pattern.match(stripped)) for key, pattern in _FIELDS.items()
                      if pattern.match(stripped)), None)
        if field is None or field[0] in meta.found_in_cartouche:
            if stripped and state == "inside":
                state = "after"
            body_lines.append(line)
            continue
        state = "inside"
        key, match = field
        value = match.group(1).strip()
        meta.found_in_cartouche.append(key)
        if key == "reference":
            meta.reference = value
        elif key == "version":
            meta.version = value
        elif key == "date":
            meta.doc_date = parse_date(value)
        elif key == "department":
            meta.department_name = value
        elif key == "author":
            meta.author_name = value
        elif key == "classification":
            meta.classification = _CLASSIFICATIONS.get(value.lower(), value)
        elif key == "diffusion":
            meta.diffusion = parse_diffusion(value)
    body = "\n".join(body_lines).strip()

    # Repli sur les propriétés du fichier puis sur son nom.
    meta.title = properties.get("title") or None
    if not meta.author_name and properties.get("author"):
        meta.author_name = properties["author"]
    if not meta.reference and properties.get("subject"):
        meta.reference = properties["subject"]
    if not meta.reference:
        m = re.search(r"([A-Z]{2,5}-[A-Z]{2,5}-\d{3})", file_name)
        meta.reference = m.group(1) if m else None
    if not meta.version:
        m = re.search(r"_v(\d+(?:\.\d+)*)", file_name, re.IGNORECASE)
        meta.version = m.group(1) if m else None
    if not meta.title:
        for line in body.split("\n"):
            cand = line.strip().lstrip("#").strip()
            if len(cand) >= 8:
                meta.title = cand[:200]
                break
    if not meta.title:
        meta.title = re.sub(r"[_-]+", " ", file_name.rsplit(".", 1)[0])
    if not meta.doc_date:
        m = re.search(r"le\s+(\d{1,2}(?:er)?\s+[a-zéû]+\s+\d{4})", body, re.IGNORECASE)
        if m:
            meta.doc_date = parse_date(m.group(1))
    meta.doc_type = infer_doc_type(meta.reference, meta.title)
    return meta, body
