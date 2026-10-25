"""Benchmark réglementaire ObliQA : chargement, profil des données et lignes de base de recherche.

ObliQA (Gokhan, Wang, Gurevych et Briscoe, 2024) rassemble 40 textes réglementaires publics de
l'ADGM découpés en passages, et des questions de conformité rattachées à 1 à 6 passages sources.
Les questions ont été générées par un LLM puis filtrées par un modèle d'inférence (NLI) ; elles ne
sont pas rédigées par des experts. Le corpus, lui, est réel.

Le module ne dépend ni de Neo4j ni d'un LLM : il fixe les lignes de base (BM25, dense, fusion RRF)
que l'architecture à base de graphe devra dépasser, en particulier sur les questions multi-passages.

Usage :
    scripts/download_obliqa.sh
    python -m benchmarks.obliqa profile
    python -m benchmarks.obliqa baselines --split test
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.settings import DATA_DIR
from evaluation.metrics import average_precision_at_k, ndcg_at_k, paired_comparison, recall_at_k, summarize

OBLIQA_DIR = DATA_DIR / "external" / "obliqa"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "evaluation" / "results" / "obliqa"
SPLITS = ("train", "dev", "test")
RRF_K = 60
STOPWORDS = frozenset(
    "the a an of to and or in on for by with is are be as that this which at from any its it such may must "
    "shall not where".split()
)
# Renvoi explicite vers une règle numérotée : « Rule 11.2.1 », « section 3.4 », « paragraphs 2.1(a) ».
CROSS_REF = re.compile(r"\b(?:Rules?|sections?|paragraphs?)\s+((?:\d+\.)+\d+(?:\([a-z0-9]+\))*)", re.IGNORECASE)


@dataclass(frozen=True)
class Passage:
    document_id: int
    passage_id: str
    text: str

    @property
    def key(self) -> str:
        return passage_key(self.document_id, self.passage_id)


@dataclass(frozen=True)
class Question:
    question_id: str
    text: str
    gold: frozenset[str]
    group: int

    @property
    def subset(self) -> str:
        return "multi" if len(self.gold) > 1 else "single"


def passage_key(document_id: int, passage_id: str) -> str:
    return f"{document_id}:{passage_id}"


def load_corpus(root: Path = OBLIQA_DIR) -> list[Passage]:
    folder = root / "StructuredRegulatoryDocuments"
    if not folder.is_dir():
        raise FileNotFoundError(f"{folder} introuvable : lancer scripts/download_obliqa.sh")
    passages = []
    for path in sorted(folder.glob("*.json"), key=lambda p: int(p.stem)):
        for row in json.loads(path.read_text(encoding="utf-8")):
            passages.append(Passage(int(row["DocumentID"]), str(row["PassageID"]), row.get("Passage") or ""))
    return passages


def load_questions(split: str, root: Path = OBLIQA_DIR) -> list[Question]:
    rows = json.loads((root / f"ObliQA_{split}.json").read_text(encoding="utf-8"))
    return [
        Question(row["QuestionID"], row["Question"],
                 frozenset(passage_key(int(p["DocumentID"]), str(p["PassageID"])) for p in row["Passages"]),
                 int(row["Group"]))
        for row in rows
    ]


def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


def _parent(passage_id: str) -> str | None:
    head, sep, _ = passage_id.rpartition(".")
    return head if sep else None


def reference_edges(passages: list[Passage]) -> dict[str, set[str]]:
    """Graphe non orienté des renvois explicites résolus vers un passage du même document."""
    ids_by_doc: dict[int, set[str]] = defaultdict(set)
    for p in passages:
        ids_by_doc[p.document_id].add(p.passage_id)
    edges: dict[str, set[str]] = defaultdict(set)
    for p in passages:
        for match in CROSS_REF.finditer(p.text):
            target = match.group(1)
            if target != p.passage_id and target in ids_by_doc[p.document_id]:
                other = passage_key(p.document_id, target)
                edges[p.key].add(other)
                edges[other].add(p.key)
    return edges


def profile(passages: list[Passage], questions_by_split: dict[str, list[Question]]) -> dict:
    """Profil descriptif du corpus et des questions, dont la connectivité des paires de passages
    attendus par le seul graphe des renvois explicites (ce qu'un graphe purement structurel apporte)."""
    words = [len(p.text.split()) for p in passages]
    keys = Counter(p.key for p in passages)
    edges = reference_edges(passages)
    out = {
        "documents": len({p.document_id for p in passages}),
        "passages": len(passages),
        "duplicate_passage_keys": sum(1 for n in keys.values() if n > 1),
        "empty_passages": sum(1 for p in passages if not p.text.strip()),
        "words_total": sum(words),
        "words_per_passage_median": float(np.median(words)),
        "passages_with_explicit_reference": sum(1 for p in passages if CROSS_REF.search(p.text)),
        "resolved_reference_edges": sum(len(v) for v in edges.values()) // 2,
        "splits": {},
    }
    for split, questions in questions_by_split.items():
        multi = [q for q in questions if q.subset == "multi"]
        pairs = linked = same_parent = same_doc = 0
        for q in multi:
            gold = sorted(q.gold)
            for i, a in enumerate(gold):
                for b in gold[i + 1:]:
                    pairs += 1
                    doc_a, pid_a = a.split(":", 1)
                    doc_b, pid_b = b.split(":", 1)
                    same_doc += doc_a == doc_b
                    if b in edges.get(a, ()):
                        linked += 1
                    elif doc_a == doc_b and _parent(pid_a) is not None and _parent(pid_a) == _parent(pid_b):
                        same_parent += 1
        out["splits"][split] = {
            "questions": len(questions),
            "passages_per_question": dict(sorted(Counter(len(q.gold) for q in questions).items())),
            "multi_passage": len(multi),
            "multi_passage_cross_document": sum(1 for q in multi if len({g.split(":")[0] for g in q.gold}) > 1),
            "gold_passages_missing_from_corpus": sum(1 for q in questions for g in q.gold if g not in keys),
            "gold_pairs": pairs,
            "gold_pairs_same_document": same_doc,
            "gold_pairs_direct_reference": linked,
            "gold_pairs_same_parent_section": same_parent,
        }
    return out


class BM25Index:
    """BM25 Okapi (k1 = 1,5 ; b = 0,75) sur index inversé en mémoire."""

    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        tokens = [tokenize(t) for t in texts]
        self.n = len(tokens)
        self.lengths = np.array([len(t) for t in tokens], dtype=float)
        self.avgdl = float(self.lengths.mean()) if self.n else 0.0
        postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, toks in enumerate(tokens):
            for term, tf in Counter(toks).items():
                postings[term].append((i, tf))
        self.postings = {t: (np.array([i for i, _ in v]), np.array([tf for _, tf in v], dtype=float))
                         for t, v in postings.items()}
        self.idf = {t: math.log(1 + (self.n - len(v[0]) + 0.5) / (len(v[0]) + 0.5)) for t, v in self.postings.items()}

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(self.n)
        for term in set(tokenize(query)):
            if term not in self.postings:
                continue
            ids, tf = self.postings[term]
            norm = self.k1 * (1 - self.b + self.b * self.lengths[ids] / self.avgdl)
            out[ids] += self.idf[term] * tf * (self.k1 + 1) / (tf + norm)
        return out


def _ranked_keys(scores: np.ndarray, keys: list[str], depth: int) -> list[str]:
    seen, ranking = set(), []
    for i in np.argsort(-scores, kind="stable"):
        if keys[i] not in seen:
            seen.add(keys[i])
            ranking.append(keys[i])
            if len(ranking) == depth:
                break
    return ranking


def rrf(rankings: list[list[str]], depth: int, k: int = RRF_K) -> list[str]:
    fused: Counter[str] = Counter()
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            fused[key] += 1.0 / (k + rank)
    return [key for key, _ in sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))[:depth]]


def run_baselines(split: str = "test", k: int = 10, pool: int = 100, root: Path = OBLIQA_DIR) -> dict:
    from retrieval.embeddings import get_embedder

    passages = load_corpus(root)
    questions = load_questions(split, root)
    keys = [p.key for p in passages]
    bm25 = BM25Index([p.text for p in passages])
    embedder = get_embedder("wordllama")
    # Les passages vides (titres seuls) reçoivent un vecteur nul : ils ne remontent jamais en dense.
    passage_vecs = np.nan_to_num(embedder.embed([p.text for p in passages]))
    question_vecs = np.nan_to_num(embedder.embed([q.text for q in questions]))

    systems = ("bm25", "dense_wordllama", "rrf_bm25_dense")
    per_question = []
    for q, qvec in zip(questions, question_vecs, strict=True):
        lexical = _ranked_keys(bm25.scores(q.text), keys, pool)
        dense = _ranked_keys(passage_vecs @ qvec, keys, pool)
        rankings = {"bm25": lexical, "dense_wordllama": dense, "rrf_bm25_dense": rrf([lexical, dense], pool)}
        relevance = dict.fromkeys(q.gold, 1)
        row = {"question_id": q.question_id, "subset": q.subset, "n_gold": len(q.gold)}
        for name in systems:
            row[name] = {
                f"recall@{k}": recall_at_k(rankings[name], relevance, k),
                f"map@{k}": average_precision_at_k(rankings[name], relevance, k),
                f"ndcg@{k}": ndcg_at_k(rankings[name], relevance, k),
            }
        per_question.append(row)

    metrics = (f"recall@{k}", f"map@{k}", f"ndcg@{k}")
    summary: dict = {}
    for name in systems:
        summary[name] = {}
        for subset in ("all", "single", "multi"):
            rows = [r for r in per_question if subset == "all" or r["subset"] == subset]
            summary[name][subset] = {m: summarize([r[name][m] for r in rows]) for m in metrics}
    comparisons = {}
    for subset in ("all", "multi"):
        rows = [r for r in per_question if subset == "all" or r["subset"] == subset]
        for other in ("dense_wordllama", "rrf_bm25_dense"):
            comparisons[f"{other}_vs_bm25_{subset}"] = paired_comparison(
                [r[other][f"recall@{k}"] for r in rows], [r["bm25"][f"recall@{k}"] for r in rows])
    return {
        "dataset": "ObliQA", "split": split, "k": k, "candidate_pool": pool,
        "embedder": embedder.name, "bm25": {"k1": bm25.k1, "b": bm25.b}, "rrf_k": RRF_K,
        "questions": len(questions), "summary": summary, "paired_recall_comparisons": comparisons,
        "per_question": per_question,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark ObliQA : profil et lignes de base")
    parser.add_argument("command", choices=("profile", "baselines"))
    parser.add_argument("--split", choices=SPLITS, default="test")
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.command == "profile":
        result = profile(load_corpus(), {s: load_questions(s) for s in SPLITS})
        target = RESULTS_DIR / "profile.json"
    else:
        result = run_baselines(args.split, args.k)
        target = RESULTS_DIR / f"baselines_{args.split}.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    shown = {k: v for k, v in result.items() if k != "per_question"}
    print(json.dumps(shown, ensure_ascii=False, indent=1))
    print(f"écrit : {target}")


if __name__ == "__main__":
    main()
