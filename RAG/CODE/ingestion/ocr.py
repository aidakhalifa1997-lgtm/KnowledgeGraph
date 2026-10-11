"""Reconnaissance optique de caractères (OCR) avec Tesseract.

Utilisée uniquement pour les pages PDF sans couche texte exploitable (documents scannés).
La page est rendue en image à 300 dpi, puis Tesseract (modèles `fra` et `eng`) en extrait le
texte. La confiance moyenne par mot (0-100) est conservée : elle alimente le contrôle qualité.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    text: str
    mean_confidence: float  # moyenne des confiances des mots reconnus, 0-100
    words: int


def ocr_image_bytes(png_bytes: bytes, languages: str = "fra+eng", timeout_s: int = 120) -> OcrResult:
    import pytesseract
    from PIL import Image

    image = Image.open(io.BytesIO(png_bytes))
    # --psm 3 : segmentation automatique de la page ; --oem 1 : moteur LSTM.
    config = "--psm 3 --oem 1"
    data = pytesseract.image_to_data(image, lang=languages, config=config, timeout=timeout_s,
                                     output_type=pytesseract.Output.DICT)
    text = pytesseract.image_to_string(image, lang=languages, config=config, timeout=timeout_s)
    confidences = [float(c) for c, w in zip(data["conf"], data["text"], strict=False) if float(c) >= 0 and w.strip()]
    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return OcrResult(text=text, mean_confidence=mean_conf, words=len(confidences))


def ocr_pdf_page(page, dpi: int = 300, languages: str = "fra+eng") -> OcrResult:
    """`page` est une page PyMuPDF."""
    pixmap = page.get_pixmap(dpi=dpi)
    return ocr_image_bytes(pixmap.tobytes("png"), languages=languages)


def tesseract_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
