"""Vérification et assainissement des réponses.

1. **Citations** : les identifiants [Cn]/[Fn] cités doivent exister dans le contexte fourni ;
   les citations inventées sont retirées et comptées.
2. **Appui documentaire** : chaque phrase porteuse d'information doit être citée ; une phrase
   citée est jugée « appuyée » si une part suffisante de ses termes figure dans les sources
   citées (approximation lexicale, cf. métriques de citation d'ALCE, Gao et al., 2023).
3. **Assainissement** : suppression des images et liens Markdown, des URL et des balises HTML
   (vecteurs classiques d'exfiltration de données) ; détection d'une fuite du prompt système.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.text import content_terms, light_stem, split_sentences

CITATION = re.compile(r"\[(C|F)(\d+)\]")
ABSTENTION = re.compile(r"je ne dispose pas d.informations suffisantes", re.IGNORECASE)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\((?:https?|ftp)://[^)]*\)")
_URL = re.compile(r"\b(?:https?|ftp)://\S+")
_HTML = re.compile(r"</?[a-zA-Z][^>]*>")
_META = re.compile(r"^(Note\s*:|Remarque\s*:|Les éléments ci-dessous|.*\(score \d)")
_PROMPT_LEAK = re.compile(r"(r[èe]gles imp[ée]ratives|tu es l'assistant de gestion des connaissances)", re.IGNORECASE)


@dataclass
class VerificationReport:
    valid_citations: list[str] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)
    sentences: int = 0
    cited_sentences: int = 0
    supported_sentences: int = 0
    unsupported: list[str] = field(default_factory=list)
    sanitized: list[str] = field(default_factory=list)
    abstention: bool = False

    @property
    def support_rate(self) -> float:
        return self.supported_sentences / self.sentences if self.sentences else 1.0


def sanitize(text: str) -> tuple[str, list[str]]:
    actions = []
    for pattern, label, repl in [(_IMAGE, "image supprimée", ""), (_LINK, "lien supprimé", r"\1"),
                                 (_URL, "URL supprimée", "[lien supprimé]"), (_HTML, "balise HTML supprimée", "")]:
        if pattern.search(text):
            actions.append(label)
            text = pattern.sub(repl, text)
    if _PROMPT_LEAK.search(text):
        actions.append("fuite du prompt système bloquée")
        text = "La réponse générée a été bloquée par les contrôles de sécurité."
    return text.strip(), actions


def _stems(text: str) -> set[str]:
    return {light_stem(t) for t in content_terms(text)}


def verify(answer: str, source_texts: dict[str, str], min_support: float = 0.3) -> tuple[str, VerificationReport]:
    """`source_texts` associe un identifiant (C1, F2...) au texte de la source."""
    report = VerificationReport()
    answer, report.sanitized = sanitize(answer)
    report.abstention = bool(ABSTENTION.search(answer))

    def replace(m: re.Match) -> str:
        cid = f"{m.group(1)}{m.group(2)}"
        if cid in source_texts:
            if cid not in report.valid_citations:
                report.valid_citations.append(cid)
            return m.group(0)
        report.invalid_citations.append(cid)
        return ""

    answer = CITATION.sub(replace, answer)
    for sentence in split_sentences(answer):
        stems = _stems(CITATION.sub("", sentence))
        if len(stems) < 3 or ABSTENTION.search(sentence) or sentence.endswith(":") or _META.match(sentence):
            continue  # phrase de liaison, d'introduction ou mention système (note, remarque, score)
        report.sentences += 1
        cited = [f"{m.group(1)}{m.group(2)}" for m in CITATION.finditer(sentence)]
        if not cited:
            report.unsupported.append(sentence)
            continue
        report.cited_sentences += 1
        source_stems = set().union(*(_stems(source_texts[c]) for c in cited if c in source_texts))
        if source_stems and len(stems & source_stems) / len(stems) >= min_support:
            report.supported_sentences += 1
        else:
            report.unsupported.append(sentence)
    return re.sub(r"[ \t]{2,}", " ", answer), report
