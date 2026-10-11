"""Classification de la question et choix de la stratégie de récupération (routage).

La classification est déterministe (indices lexicaux + entités reconnues), donc rapide,
gratuite, reproductible et explicable. Elle n'a pas besoin d'être parfaite : elle module
seulement le poids du graphe et la profondeur d'exploration.

| Type        | Exemple                                                     | Route                             |
|-------------|-------------------------------------------------------------|-----------------------------------|
| factual     | « Quel est le délai d'accusé de réception ? »               | hybride, graphe faible (0,5), 1 saut |
| relational  | « Qui fait partie de l'équipe du projet Sentinel ? »        | hybride + graphe (1,0), 2 sauts   |
| multi_hop   | « Quel projet dépend d'un projet piloté par L. Chraibi ? »  | hybride + graphe (1,5), 2 sauts   |
| expert      | « Qui est expert en machine learning ? »                    | hybride + graphe + classement d'experts |
| ambiguous   | « Qui est responsable de Sentinel ? »                       | hybride + graphe, ambiguïté signalée |
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.text import content_terms, normalize_key
from retrieval.graph import detect_intent, intent_groups

_EXPERT = re.compile(r"\b(experts?|expertise|competen\w*|speciali\w*|maitris\w*|qui peut m.aider|vers qui|"
                     r"qui contacter|qui connait|referents?)\b")
_MULTI_HOP = re.compile(
    r"(\b(d'un|d'une|du|de la|de l')\s+(projet|programme|application|systeme|procedure|outil|consultant|personne|"
    r"collaborat\w*)\b.*\b(pilot\w*|responsable|livr\w*|depend\w*|sponsor\w*|dirig\w*|utilis\w*|proprietaire)\b)"
    r"|(\bdont\b.*\b(est|sont)\b)|directement ou indirectement|\bqui a livre\b"
    r"|(\b(travaill\w*|appartien\w*)\b.*\b(qui|dont)\b)")


@dataclass
class Route:
    question_type: str
    strategy: str
    graph_weight: float
    max_hops: int
    reason: str


def classify(question: str, seeds: list[dict], ambiguous: list[dict]) -> Route:
    q = normalize_key(question)
    intents = detect_intent(question)
    terms = content_terms(question)
    if ambiguous:
        return Route("ambiguous", "hybrid_graph", 1.0, 2,
                     "nom ambigu dans la question : " + ", ".join(a["surface"] for a in ambiguous))
    if _EXPERT.search(q):
        return Route("expert", "hybrid_graph", 1.0, 1, "recherche d'expertise")
    if seeds and (_MULTI_HOP.search(q) or intent_groups(question) >= 3):
        return Route("multi_hop", "hybrid_graph", 1.5, 2, "question à plusieurs relations successives")
    if seeds and intents:
        return Route("relational", "hybrid_graph", 1.0, 2, "question portant sur des relations entre entités")
    if not seeds and len(terms) <= 3:
        return Route("ambiguous", "hybrid_graph", 0.5, 1, "question très courte sans entité identifiable")
    return Route("factual", "hybrid_graph", 0.5, 1, "question factuelle")
