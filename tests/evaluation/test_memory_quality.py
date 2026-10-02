from decimal import Decimal

import pytest

from kestri.errors import BudgetExceeded
from kestri.redaction import Redactor
from scripts.memory_evaluation.common import (
    EvaluationLedger,
    extraction_metrics,
    history_corpus,
    history_metrics,
    selection_metrics,
)


def test_extraction_requires_action_and_counts_every_operation() -> None:
    cases = [
        {"id": "positive", "expected": [{"terms": [["SQLite"]], "action": "replace"}]},
        {"id": "negative", "expected": []},
    ]
    results = {
        "positive": {
            "operations": [
                {"content": "SQLite", "action": "create"},
                {"content": "SQLite", "action": "replace"},
                {"content": "SQLite", "action": "replace"},
            ],
            "error": None,
        },
        "negative": {"operations": [{"content": "bad", "action": "create"}], "error": None},
    }
    metrics = extraction_metrics(cases, results)
    assert metrics["active_precision"] == 0.25
    assert metrics["direct_recall"] == 1
    assert metrics["false_extraction_rate"] == 1


def test_final_selection_counts_false_injection_not_candidates() -> None:
    cases = [{"id": "positive", "relevant_ids": ["a", "b"]}, {"id": "negative", "relevant_ids": []}]
    metrics = selection_metrics(
        cases,
        {
            "positive": {"selected_ids": ["a"], "error": None},
            "negative": {"selected_ids": [], "error": None},
        },
    )
    assert metrics["recall_at_8"] == 0.5
    assert metrics["false_related_injection_rate"] == 0
    assert selection_metrics([], {})["recall_at_8"] is None


async def test_evaluation_ledger_keeps_unknown_reservations() -> None:
    ledger = EvaluationLedger(Decimal(".000010"), Redactor([]))
    first = await ledger.reserve("run", "model", 7)
    with pytest.raises(BudgetExceeded):
        await ledger.reserve("run", "model", 4)
    await ledger.settle(first, {}, 2)
    await ledger.reserve("run", "model", 8)
    assert ledger.report()["estimated_and_unknown_micro_usd"] == 10
    assert ledger.report()["states"] == {"recorded": 1, "unknown": 1}


def test_history_corpus_uses_complete_json_and_disjoint_project_splits() -> None:
    turns, cases = history_corpus()
    assert len(turns) == 20 and len(cases) == 60
    assert all(
        [message["role"] for message in turn["messages"]] == ["owner", "assistant"]
        for turn in turns
    )
    dev = {turn["id"] for turn in turns if turn["split"] == "development"}
    hold = {turn["id"] for turn in turns if turn["split"] == "holdout"}
    assert not dev & hold
    assert history_metrics([], {})["recall_at_5"] is None


async def test_synthetic_answer_handles_require_search_before_full_read() -> None:
    import json

    from kestri.errors import PolicyDenied
    from scripts.memory_evaluation.history_answer import scenario_tools

    turns, _ = history_corpus()
    calls: list[str] = []
    search, read = scenario_tools(turns[:2], calls)
    with pytest.raises(PolicyDenied, match="HistoryHandleUnavailable"):
        await read.ainvoke({"segment_id": turns[0]["id"]})
    response = json.loads(await search.ainvoke({"query": "历史决定", "limit": 1}))
    assert len(response["results"]) == 1
    full = json.loads(await read.ainvoke({"segment_id": turns[0]["id"]}))
    assert not full["truncated"]
    assert [message["role"] for message in full["messages"]] == ["owner", "assistant"]
    with pytest.raises(PolicyDenied):
        await read.ainvoke({"segment_id": turns[1]["id"]})
    assert calls == ["search_history", "read_history_segment"]
