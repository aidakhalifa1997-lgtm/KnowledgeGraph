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


def fuse_top_k(rankings: dict[str, list[str]], top_k: int, k: int = 60, weights: dict[str, float] | None = None,
               guarantee: int = 1) -> list[tuple[str, float, dict[str, int]]]:
    """Fusion RRF tronquée à `top_k`, avec garantie par source.

    Limite connue de RRF : un élément classé 1er par une seule source (ex. passage contenant
    l'acronyme exact « RTO », trouvé par BM25 seul) obtient 1/(k+1) ≈ 0,016 et peut être
    devancé par des éléments moyens mais présents dans toutes les listes (3/(k+4) ≈ 0,047).
    La garantie réserve une place aux `guarantee` premiers éléments de chaque source active ;
    ils remplacent les derniers éléments non garantis. `guarantee=0` donne la RRF pure.
    """
    weights = weights or {}
    fused = reciprocal_rank_fusion(rankings, k=k, weights=weights)
    selected = fused[:top_k]
    if guarantee <= 0:
        return selected
    required: list[str] = []
    for source, items in rankings.items():
        if weights.get(source, 1.0) > 0:
            required += [item for item in items[:guarantee] if item not in required]
    by_id = {item: entry for entry in fused for item in [entry[0]]}
    chosen = {item for item, _, _ in selected}
    for item in required:
        if item in chosen or item not in by_id:
            continue
        if len(selected) >= top_k:
            for pos in range(len(selected) - 1, -1, -1):
                if selected[pos][0] not in required:
                    chosen.discard(selected.pop(pos)[0])
                    break
            else:
                break  # toutes les places sont déjà occupées par des éléments garantis
        selected.append(by_id[item])
        chosen.add(item)
    return sorted(selected, key=lambda e: (-e[1], e[0]))
