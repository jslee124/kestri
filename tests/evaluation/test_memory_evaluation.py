"""Check scoring denominators and prevent holdout-driven calibration."""

import copy

import pytest

from scripts.evaluate_memory import load_corpus, score, summarize


def test_corpus_is_labeled_and_not_owner_data() -> None:
    corpus, digest = load_corpus()
    assert len(corpus["cases"]) == 120
    assert len(digest) == 64
    assert all(
        case["relevant_ids"]
        or case["category"] in {"temporary_emotion", "hypothetical", "quotation", "unrelated"}
        for case in corpus["cases"]
    )


def test_recall_counts_labels_and_limits_to_eight() -> None:
    cases = [{"id": "positive", "relevant_ids": ["a", "b"]}, {"id": "negative", "relevant_ids": []}]
    metrics = summarize(cases, {"positive": ["a", *["x"] * 7, "b"], "negative": ["x"]})
    assert metrics["relevant_labels"] == 2
    assert metrics["retrieved_relevant_at_8"] == 1
    assert metrics["recall_at_8"] == 0.5
    assert metrics["false_candidate_rate"] == 1
    assert "false_injection_rate" not in metrics


def test_no_labels_is_unmeasured_not_perfect() -> None:
    result = summarize([], {})
    assert result["recall_at_8"] is None
    assert result["false_candidate_rate"] is None


def test_holdout_cannot_choose_threshold() -> None:
    corpus = {
        "facts": [{"id": "a", "content": "猫咪"}],
        "cases": [
            {"id": "dev", "query": "动物", "relevant_ids": ["a"], "split": "development"},
            {"id": "hold", "query": "植物", "relevant_ids": [], "split": "holdout"},
        ],
    }
    vectors = [(1.0, 0.0), (0.6, 0.8), (1.0, 0.0)]
    first = score(corpus, vectors)
    altered = copy.deepcopy(corpus)
    altered["cases"][1]["relevant_ids"] = ["a"]
    second = score(altered, vectors)
    assert first["development_recommendation"] == second["development_recommendation"] == 0.6
    assert first["thresholds"][8]["holdout"] != second["thresholds"][8]["holdout"]


def test_vector_count_mismatch_cannot_report_quality() -> None:
    corpus, _ = load_corpus()
    with pytest.raises(ValueError, match="VectorCountMismatch"):
        score(corpus, [])
