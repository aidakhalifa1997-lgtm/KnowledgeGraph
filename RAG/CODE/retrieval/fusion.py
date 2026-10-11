"""Fusion de classements par Reciprocal Rank Fusion (Cormack, Clarke et Büttcher, 2009).

Pour chaque élément d présent dans un ou plusieurs classements :
    RRF(d) = Σ_i  w_i / (k + rang_i(d))
avec k = 60 (valeur de l'article) et w_i un poids optionnel par source. Les scores bruts des
sources (BM25, cosinus, PageRank) ne sont pas comparables entre eux ; seuls les rangs le sont.
"""

from __future__ import annotations


def reciprocal_rank_fusion(rankings: dict[str, list[str]], k: int = 60,
                           weights: dict[str, float] | None = None) -> list[tuple[str, float, dict[str, int]]]:
    """Retourne [(identifiant, score, {source: rang})] trié par score décroissant."""
    weights = weights or {}
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for source, items in rankings.items():
        w = weights.get(source, 1.0)
        if w <= 0:
            continue
        for rank, item in enumerate(items, start=1):
            scores[item] = scores.get(item, 0.0) + w / (k + rank)
            ranks.setdefault(item, {})[source] = rank
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(item, round(score, 6), ranks[item]) for item, score in ordered]
