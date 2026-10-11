"""Évaluation de la suffisance du contexte (inspirée de CRAG, Yan et al., 2024).

Avant de générer, on vérifie que le contexte récupéré couvre réellement la question :
- couverture pondérée des termes de la question : chaque terme porteur de sens est pondéré par
  son IDF (un terme rare comme « budget » ou « DPO » compte beaucoup plus qu'un terme fréquent
  comme « procédure ») ; si les termes rares sont absents du contexte, il est probable que la
  réponse n'y soit pas ;
- couverture des entités : les entités citées dans la question doivent apparaître dans le
  contexte (texte ou faits du graphe).

Le contexte est jugé suffisant si la couverture pondérée dépasse un seuil fixé a priori
(0,55) et si au moins la moitié des entités sont couvertes. Une analyse de sensibilité au
seuil est fournie dans l'évaluation.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from core.text import content_terms, fold_accents, light_stem, normalize_key, text_units

_QUANTITY = re.compile(r"\d+(?:[.,]\d+)?\s*(%|mois|jours?|heures?|minutes?|ans|mad)(?!\w)", re.IGNORECASE)
# Nombre « nu » d'au moins deux chiffres (score, montant), hors années et codes (PRC-KYC-001).
_BARE_NUMBER = re.compile(r"(?<![\w-])(?!(?:19|20)\d\d\b)\d{2,}(?:[ .,]\d{3})*(?![\w-])")
_VALUE_QUESTION = re.compile(r"\b(combien|quel(le)?s? (est|sont) (le|la|les) (delai|seuil|taux|frequence|plafond|"
                             r"score|indicateur|pourcentage|rto|rpo|montant)|dans quel delai|sous quel delai|"
                             r"en dessous de quel|quel (delai|seuil|taux|pourcentage|indicateur|score|montant))")


def term_key(token: str) -> str:
    """Clé de comparaison des termes : racine Snowball tronquée à 6 caractères (« plafond » et
    « plafonné » se rejoignent, « délégué » et « délégation » restent distincts)."""
    return light_stem(token)[:6]

# Mots de la question qui ne portent pas l'information recherchée.
QUESTION_FILLERS = {
    "aider", "sujet", "question", "savoir", "connaitre", "trouver", "tourner", "donner", "obtenu", "obtenue",
    "faut", "agit", "existe", "information", "informations", "concernant", "propos", "quoi", "dire", "banque",
    "toujours", "actuellement", "ensuite", "dessous", "dessus",
}


class TermStatistics:
    """Fréquences documentaires des termes (racinisés) sur l'ensemble des passages indexés."""

    def __init__(self, texts: list[str]) -> None:
        self.n = max(1, len(texts))
        self.df: Counter[str] = Counter()
        for text in texts:
            self.df.update({term_key(t) for t in content_terms(text)})

    def idf(self, stem: str) -> float:
        return math.log((self.n + 1) / (self.df.get(stem, 0) + 1)) + 1.0


@dataclass
class Sufficiency:
    sufficient: bool
    term_coverage: float
    entity_coverage: float
    missing_terms: list[str]
    reason: str


def assess(question: str, context_texts: list[str], seed_surfaces: list[list[str]], stats: TermStatistics,
           threshold: float = 0.55) -> Sufficiency:
    """`seed_surfaces` : pour chaque entité de la question, ses formes possibles (nom et alias).

    Règle de couverture des entités : avec une ou deux entités dans la question, toutes doivent
    apparaître dans le contexte (« le RTO de CoreNova » exige à la fois « RTO » et « CoreNova ») ;
    au-delà, au moins la moitié."""
    if not context_texts:
        return Sufficiency(False, 0.0, 0.0, [], "aucun passage récupéré")
    context_stems = {term_key(t) for text in context_texts for t in content_terms(text)}
    seed_tokens = {term_key(t) for surfaces in seed_surfaces for name in surfaces for t in content_terms(name)}
    terms = [t for t in dict.fromkeys(content_terms(question)) if fold_accents(t) not in QUESTION_FILLERS]
    weighted = [(t, stats.idf(term_key(t))) for t in terms if term_key(t) not in seed_tokens]
    total = sum(w for _, w in weighted)
    covered = sum(w for t, w in weighted if term_key(t) in context_stems)
    term_coverage = covered / total if total else 1.0
    missing = [t for t, _ in weighted if term_key(t) not in context_stems]

    context_key = " " + normalize_key(" ".join(context_texts)) + " "
    if seed_surfaces:
        present = 0
        for surfaces in seed_surfaces:
            if any(f" {normalize_key(name)} " in context_key for name in surfaces if normalize_key(name)):
                present += 1
            else:
                missing.append(surfaces[0])
        entity_coverage = present / len(seed_surfaces)
        required = 1.0 if len(seed_surfaces) <= 2 else 0.5
    else:
        entity_coverage, required = 1.0, 0.0
    sufficient = term_coverage >= threshold and entity_coverage >= required
    # Type de réponse attendu : une question qui demande une valeur (délai, taux, RTO...) exige
    # qu'une phrase du contexte associe une quantité chiffrée à l'objet de la question.
    if sufficient and _VALUE_QUESTION.search(normalize_key(question)):
        surfaces = [f" {normalize_key(n)} " for group in seed_surfaces for n in group if normalize_key(n)]
        focus = {term_key(t) for t, _ in weighted}
        top_term = term_key(max(weighted, key=lambda x: x[1])[0]) if weighted else None

        def answers_value(sentence: str) -> bool:
            if not (_QUANTITY.search(sentence) or _BARE_NUMBER.search(sentence)):
                return False
            key = f" {normalize_key(sentence)} "
            if any(sf in key for sf in surfaces):
                return True
            terms_here = {term_key(t) for t in content_terms(sentence)}
            return len(focus & terms_here) >= 2 and (top_term is None or top_term in terms_here)

        # Unités de sens (et non phrases isolées) : une puce « risque élevé : 12 mois » se lit
        # avec sa phrase d'introduction (« La fréquence de revue périodique est... : »).
        if not any(answers_value(unit) for text in context_texts for unit in text_units(text)):
            sufficient = False
            missing.append("valeur chiffrée")
    if sufficient:
        reason = "contexte couvrant la question"
    elif entity_coverage < required:
        reason = "entités de la question absentes du contexte : " + ", ".join(missing[-3:])
    elif "valeur chiffrée" in missing:
        reason = "aucune valeur chiffrée associée à l'objet de la question dans le contexte"
    else:
        reason = "termes clés absents du contexte : " + ", ".join(missing[:5])
    return Sufficiency(sufficient, round(term_coverage, 3), round(entity_coverage, 3), missing, reason)
