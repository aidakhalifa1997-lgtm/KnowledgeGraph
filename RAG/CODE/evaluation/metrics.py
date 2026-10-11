"""Métriques d'évaluation (implémentations de référence, sans dépendance externe).

Recherche d'information (classement de documents, pertinence graduée 0/1/2) :
- Recall@k    : part des documents pertinents retrouvés dans les k premiers ;
- Precision@k : part des k premiers résultats qui sont pertinents (dénominateur k, convention
                usuelle : un système qui renvoie moins de k documents est pénalisé) ;
- MRR         : inverse du rang du premier document pertinent (0 si aucun) ;
- nDCG@k      : gain cumulé actualisé normalisé (Järvelin et Kekäläinen, 2002), gain = 2^rel - 1.

Statistiques :
- intervalle de confiance à 95 % de la moyenne par bootstrap percentile (Efron et Tibshirani, 1993),
  graine fixée pour la reproductibilité ;
- comparaison appariée de deux systèmes sur les mêmes questions : différence moyenne avec IC
  bootstrap apparié, et test exact des signes (questions où les systèmes diffèrent).
Avec 66 questions, ces intervalles sont larges : ils servent à ne pas surinterpréter des écarts.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence


def recall_at_k(ranking: Sequence[str], relevance: dict[str, int], k: int) -> float:
    relevant = {d for d, r in relevance.items() if r > 0}
    if not relevant:
        return 0.0
    return len(relevant & set(ranking[:k])) / len(relevant)


def precision_at_k(ranking: Sequence[str], relevance: dict[str, int], k: int) -> float:
    return sum(1 for d in ranking[:k] if relevance.get(d, 0) > 0) / k


def reciprocal_rank(ranking: Sequence[str], relevance: dict[str, int]) -> float:
    for i, d in enumerate(ranking, start=1):
        if relevance.get(d, 0) > 0:
            return 1.0 / i
    return 0.0


def dcg(gains: Sequence[float]) -> float:
    return sum(g / math.log2(i + 1) for i, g in enumerate(gains, start=1))


def ndcg_at_k(ranking: Sequence[str], relevance: dict[str, int], k: int) -> float:
    gains = [2 ** relevance.get(d, 0) - 1 for d in ranking[:k]]
    ideal = sorted((2 ** r - 1 for r in relevance.values() if r > 0), reverse=True)[:k]
    best = dcg(ideal)
    return dcg(gains) / best if best else 0.0


def ranking_metrics(ranking: Sequence[str], relevance: dict[str, int], ks: Sequence[int] = (1, 3, 5)) -> dict:
    out = {"mrr": reciprocal_rank(ranking, relevance)}
    for k in ks:
        out[f"recall@{k}"] = recall_at_k(ranking, relevance, k)
        out[f"precision@{k}"] = precision_at_k(ranking, relevance, k)
        out[f"ndcg@{k}"] = ndcg_at_k(ranking, relevance, k)
    return out


def safe_ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def bootstrap_ci(values: Sequence[float], n_resamples: int = 2000, seed: int = 42, alpha: float = 0.05) -> tuple[float, float]:
    values = list(values)
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(statistics.fmean(rng.choices(values, k=n)) for _ in range(n_resamples))
    return (percentile(means, alpha / 2), percentile(means, 1 - alpha / 2))


def summarize(values: Sequence[float]) -> dict:
    values = [float(v) for v in values]
    if not values:
        return {"n": 0, "mean": None, "ci95": [None, None]}
    lo, hi = bootstrap_ci(values)
    return {"n": len(values), "mean": round(statistics.fmean(values), 4), "ci95": [round(lo, 4), round(hi, 4)]}


def sign_test(a: Sequence[float], b: Sequence[float]) -> dict:
    """Test exact des signes bilatéral sur des mesures appariées (ex æquo ignorés)."""
    wins = sum(1 for x, y in zip(a, b, strict=True) if x > y)
    losses = sum(1 for x, y in zip(a, b, strict=True) if x < y)
    n = wins + losses
    if n == 0:
        return {"wins": 0, "losses": 0, "ties": len(a), "p_value": 1.0}
    tail = sum(math.comb(n, i) for i in range(0, min(wins, losses) + 1)) / 2 ** n
    return {"wins": wins, "losses": losses, "ties": len(a) - n, "p_value": round(min(1.0, 2 * tail), 4)}


def paired_comparison(a: Sequence[float], b: Sequence[float], n_resamples: int = 2000, seed: int = 7) -> dict:
    """Différence moyenne a - b avec IC bootstrap apparié (on rééchantillonne les questions)."""
    diffs = [x - y for x, y in zip(a, b, strict=True)]
    lo, hi = bootstrap_ci(diffs, n_resamples=n_resamples, seed=seed)
    return {"mean_diff": round(statistics.fmean(diffs), 4) if diffs else None, "ci95": [round(lo, 4), round(hi, 4)],
            **sign_test(a, b)}
