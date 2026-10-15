"""Contrôle qualité des documents avant intégration.

Chaque contrôle produit un constat (`QualityIssue`) de gravité info / warning / error.
Un constat `error` entraîne le rejet du document (statut `rejected`) : il est tracé dans le
graphe (nœud Document + IngestionRun) mais n'alimente ni la recherche ni les relations.
"""

from __future__ import annotations

from core.models import QualityIssue
from core.text import STOPWORDS, tokenize

MIN_CHARS = 150
MIN_ALPHA_RATIO = 0.55
OCR_WARNING = 70.0
OCR_ERROR = 45.0


def assess_quality(text: str, *, ocr_confidence: float | None, reference: str | None, doc_date, author: str | None,
                   department: str | None, diffusion_declared: bool = True) -> tuple[float, list[QualityIssue], str]:
    issues: list[QualityIssue] = []
    stripped = text.strip()

    # Refus par défaut : sans ligne « Diffusion » dans le cartouche, on ne sait pas à qui le document
    # peut être montré. Il n'est donc pas publié (et non diffusé à tous par défaut).
    if not diffusion_declared:
        issues.append(QualityIssue(code="missing_diffusion", severity="error",
                                   message="diffusion non déclarée dans le cartouche : document non publié "
                                           "(refus par défaut), à corriger par son propriétaire"))

    if len(stripped) < MIN_CHARS:
        issues.append(QualityIssue(code="text_too_short", severity="error",
                                   message=f"texte extrait trop court ({len(stripped)} caractères)"))
    letters = sum(ch.isalpha() for ch in stripped)
    non_space = sum(not ch.isspace() for ch in stripped) or 1
    alpha_ratio = letters / non_space
    if stripped and alpha_ratio < MIN_ALPHA_RATIO:
        issues.append(QualityIssue(code="noisy_text", severity="warning",
                                   message=f"proportion de lettres faible ({alpha_ratio:.0%}) : texte bruité ?"))

    if ocr_confidence is not None:
        if ocr_confidence < OCR_ERROR:
            issues.append(QualityIssue(code="ocr_unreadable", severity="error",
                                       message=f"confiance OCR très faible ({ocr_confidence:.0f}/100)"))
        elif ocr_confidence < OCR_WARNING:
            issues.append(QualityIssue(code="ocr_low_confidence", severity="warning",
                                       message=f"confiance OCR moyenne ({ocr_confidence:.0f}/100) : vérifier le texte"))
        else:
            issues.append(QualityIssue(code="ocr_used", severity="info",
                                       message=f"texte obtenu par OCR (confiance {ocr_confidence:.0f}/100)"))

    tokens = tokenize(stripped)
    language = "fr"
    if tokens:
        fr_ratio = sum(t in STOPWORDS for t in tokens) / len(tokens)
        if fr_ratio < 0.08:
            language = "inconnue"
            issues.append(QualityIssue(code="language_unknown", severity="warning",
                                       message="langue française non reconnue (peu de mots outils)"))

    for value, code, label in [(reference, "missing_reference", "référence"), (doc_date, "missing_date", "date"),
                               (author, "missing_author", "rédacteur"), (department, "missing_department",
                                                                          "direction propriétaire")]:
        if not value:
            issues.append(QualityIssue(code=code, severity="warning", message=f"métadonnée manquante : {label}"))

    score = 1.0
    for issue in issues:
        score -= {"info": 0.0, "warning": 0.1, "error": 0.5}[issue.severity]
    return max(0.0, round(score, 2)), issues, language
