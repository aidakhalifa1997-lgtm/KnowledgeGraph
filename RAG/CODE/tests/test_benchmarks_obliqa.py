"""Tests du module de benchmark ObliQA sur un mini-corpus au format d'origine (sans téléchargement)."""

from __future__ import annotations

import json

import pytest

from benchmarks.obliqa import BM25Index, Passage, load_corpus, load_questions, profile, reference_edges, rrf
from evaluation.metrics import average_precision_at_k


def test_average_precision_follows_trec_eval_convention():
    relevance = {"a": 1, "b": 1, "c": 1}
    # Pertinents aux rangs 1 et 3, un pertinent jamais retrouvé : (1/1 + 2/3) / 3.
    assert average_precision_at_k(["a", "x", "b", "y"], relevance, 10) == pytest.approx((1 + 2 / 3) / 3)
    assert average_precision_at_k(["x", "a"], relevance, 1) == 0.0
    assert average_precision_at_k(["a"], {}, 10) == 0.0


def test_rrf_rewards_agreement_between_rankings():
    fused = rrf([["a", "b", "c"], ["b", "a", "d"]], depth=3)
    assert set(fused[:2]) == {"a", "b"}
    assert "c" in fused or "d" in fused


def test_bm25_ranks_the_passage_sharing_rare_terms_first():
    index = BM25Index(["capital adequacy requirements for banks",
                       "the fund manager must keep records",
                       "records of anti money laundering checks"])
    scores = index.scores("money laundering records")
    assert scores.argmax() == 2
    assert scores[0] == 0.0


def test_reference_edges_resolve_only_existing_rules_of_the_same_document():
    passages = [Passage(1, "2.1", "See Rule 2.2 and Rule 9.9."), Passage(1, "2.2", "Obligation."),
                Passage(2, "2.2", "Another document.")]
    edges = reference_edges(passages)
    assert edges["1:2.1"] == {"1:2.2"}
    assert "2:2.2" not in edges


def test_loaders_and_profile_on_the_original_format(tmp_path):
    folder = tmp_path / "StructuredRegulatoryDocuments"
    folder.mkdir()
    rows = [{"ID": "u1", "DocumentID": 1, "PassageID": "1.1", "Passage": "A Person must comply with Rule 1.2."},
            {"ID": "u2", "DocumentID": 1, "PassageID": "1.2", "Passage": "Records must be kept."},
            {"ID": "u3", "DocumentID": 1, "PassageID": "1.3", "Passage": ""}]
    (folder / "1.json").write_text(json.dumps(rows), encoding="utf-8")
    questions = [{"QuestionID": "q1", "Question": "What must be kept?", "Group": 1,
                  "Passages": [{"DocumentID": 1, "PassageID": "1.2", "Passage": "Records must be kept."}]},
                 {"QuestionID": "q2", "Question": "How to comply?", "Group": 2,
                  "Passages": [{"DocumentID": 1, "PassageID": "1.1", "Passage": "..."},
                               {"DocumentID": 1, "PassageID": "1.2", "Passage": "..."}]}]
    (tmp_path / "ObliQA_test.json").write_text(json.dumps(questions), encoding="utf-8")

    passages = load_corpus(tmp_path)
    loaded = load_questions("test", tmp_path)
    assert [q.subset for q in loaded] == ["single", "multi"]
    stats = profile(passages, {"test": loaded})
    assert stats["passages"] == 3 and stats["empty_passages"] == 1
    assert stats["resolved_reference_edges"] == 1
    split = stats["splits"]["test"]
    assert split["multi_passage"] == 1 and split["gold_pairs"] == 1
    assert split["gold_pairs_direct_reference"] == 1
    assert split["gold_passages_missing_from_corpus"] == 0


def test_missing_corpus_points_to_the_download_script(tmp_path):
    with pytest.raises(FileNotFoundError, match="download_obliqa"):
        load_corpus(tmp_path)
