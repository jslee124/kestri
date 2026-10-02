"""Live synthetic extraction/selection and history-recipe evaluation; no database or Telegram."""

import asyncio
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from langchain_core.language_models import BaseChatModel

from kestri.agent.budget import RunControl, micro_usd
from kestri.errors import BudgetExceeded
from kestri.history.retriever import segment
from kestri.memory.retriever import lexical_rank, reciprocal_rank_fusion
from kestri.redaction import Redactor
from kestri.settings import ResearchSettings
from kestri.storage.store import Row, Store

ROOT = Path(__file__).resolve().parents[2]
EXTRACTION = ROOT / "evals/memory/chinese-extraction-v2.json"
EMBEDDINGS = ROOT / "docs/development/evidence/memory-embedding-v1.json"
SCORER = "active-extraction-and-final-selection-v1"


class EvaluationLedger:
    """Private in-memory reservations, including unknown calls, across the whole evaluation.

    This deliberately does not pretend to be the production database ledger. Model adapters
    and admission middleware are shared; persistence and races are tested separately.
    """

    def __init__(self, cap: Decimal, redactor: Redactor) -> None:
        self.cap = micro_usd(cap)
        self.redactor = redactor
        self.rows: dict[str, Row] = {}
        self.events: list[str] = []

    async def reserve(self, run_id: str, kind: str, amount: int, *args: Any, **kwargs: Any) -> str:
        if sum(row["amount"] for row in self.rows.values()) + amount > self.cap:
            raise BudgetExceeded("EvaluationBudgetExceeded")
        identity = str(uuid4())
        self.rows[identity] = {"kind": kind, "amount": amount, "state": "unknown", "metadata": {}}
        return identity

    async def settle(self, reservation: str, metadata: Row, amount: int | None = None) -> None:
        row = self.rows[reservation]
        row.update(state="recorded", metadata=metadata)
        if amount is not None:
            row["amount"] = amount
        if sum(item["amount"] for item in self.rows.values()) > self.cap:
            raise BudgetExceeded("EvaluationUsageExceeded")

    async def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        # charged_embedding sets metadata before HTTP. No SQL is executed here.
        self.rows[str(params[1])]["metadata"] = params[0].obj

    async def event(self, run_id: str, kind: str, metadata: Row) -> None:
        self.events.append(kind)

    def report(self) -> Row:
        return {
            "cap_micro_usd": self.cap,
            "estimated_and_unknown_micro_usd": sum(row["amount"] for row in self.rows.values()),
            "requests": len(self.rows),
            "states": dict(Counter(row["state"] for row in self.rows.values())),
            "kinds": dict(Counter(row["kind"] for row in self.rows.values())),
            "event_counts": dict(Counter(self.events)),
            "accounting": "in-memory evaluation estimates; outside production ledger; not invoices",
        }


class EvaluationControl(RunControl):
    def __init__(self, ledger: EvaluationLedger) -> None:
        super().__init__(cast(Store, ledger), str(uuid4()))

    async def ensure_active(self) -> None:
        if self.cancel.is_set():
            raise asyncio.CancelledError


def extraction_metrics(cases: list[Row], results: dict[str, Row]) -> Row:
    labels = matched = active = 0
    negatives = false_negative_cases = 0
    for case in cases:
        expected = case["expected"]
        operations = results[case["id"]]["operations"]
        labels += len(expected)
        active += len(operations)
        available = list(range(len(expected)))
        for operation in operations:
            text = operation["content"].casefold()
            hit = next(
                (
                    index
                    for index in available
                    if operation["action"] == expected[index]["action"]
                    and all(
                        any(term.casefold() in text for term in alternatives)
                        for alternatives in expected[index]["terms"]
                    )
                ),
                None,
            )
            if hit is not None:
                matched += 1
                available.remove(hit)
        if not expected:
            negatives += 1
            false_negative_cases += bool(operations)
    return {
        "expected_active_labels": labels,
        "validated_active_operations": active,
        "matched_active_labels": matched,
        "active_precision": matched / active if active else None,
        "direct_recall": matched / labels if labels else None,
        "negative_cases": negatives,
        "negative_cases_with_active_operations": false_negative_cases,
        "false_extraction_rate": false_negative_cases / negatives if negatives else None,
        "failed_cases": sum(bool(results[case["id"]]["error"]) for case in cases),
    }


def selection_metrics(cases: list[Row], results: dict[str, Row]) -> Row:
    expected = sum(len(case["relevant_ids"]) for case in cases)
    found = sum(
        len(set(case["relevant_ids"]) & set(results[case["id"]]["selected_ids"][:8]))
        for case in cases
    )
    negatives = [case for case in cases if not case["relevant_ids"]]
    errors = sum(bool(results[case["id"]]["selected_ids"]) for case in negatives)
    return {
        "expected_labels": expected,
        "selected_relevant_at_8": found,
        "recall_at_8": found / expected if expected else None,
        "negative_queries": len(negatives),
        "negative_queries_with_related_injection": errors,
        "false_related_injection_rate": errors / len(negatives) if negatives else None,
        "scope": "assembled related facts; always-present communication profile excluded",
        "failed_cases": sum(bool(results[case["id"]]["error"]) for case in cases),
    }


def selection_candidates(corpus: Row, evidence: Row, threshold: float) -> dict[str, list[Row]]:
    facts = corpus["facts"]
    scores = {case["id"]: case["similarities"] for case in evidence["metrics"]["cases"]}
    result = {}
    for case in corpus["cases"]:
        dense = sorted(
            [fact for fact in facts if scores[case["id"]][fact["id"]] >= threshold],
            key=lambda fact: (-scores[case["id"]][fact["id"]], fact["id"]),
        )[:20]
        result[case["id"]] = reciprocal_rank_fusion(lexical_rank(facts, case["query"]), dense)
    return result


def history_corpus() -> tuple[list[Row], list[Row]]:
    """Distinct synthetic project domains across splits, same-topic near-neighbor distractors."""
    turns: list[Row] = []
    cases: list[Row] = []
    names = ["云杉", "石桥", "海燕", "竹林", "青石", "白鹭", "枫叶", "溪流", "松果", "山雀"]
    for index, name in enumerate(names):
        split = "development" if index < 5 else "holdout"
        for variant, database in enumerate(["SQLite", "PostgreSQL"]):
            owner = f"我决定{name}项目的版本{variant + 1}使用{database}，入口采用命令行。"
            rows = [
                {
                    "id": 10 * index + 2 * variant + offset + 1,
                    "telegram_id": 1000 + 10 * index + 2 * variant + offset,
                    "direction": direction,
                    "created_at": datetime(2026, 10, 1, tzinfo=UTC),
                    "content": content,
                }
                for offset, (direction, content) in enumerate(
                    [("in", owner), ("out", f"收到，你为{name}版本{variant + 1}选择了{database}。")]
                )
            ]
            turn = segment(rows)
            assert turn
            turn["split"] = split
            turns.append(turn)
            for query in (
                f"{name}版本{variant + 1}当时选了什么数据库？",
                f"回查{name}项目第{variant + 1}版的数据存储决定",
            ):
                cases.append(
                    {
                        "id": f"h-{index}-{variant}-{len(cases)}",
                        "query": query,
                        "split": split,
                        "relevant_ids": [turn["id"]],
                    }
                )
        for query in (f"{name}项目预算多少钱？", f"我对{name}项目的部署机房作过什么决定？"):
            cases.append(
                {
                    "id": f"n-{index}-{len(cases)}",
                    "query": query,
                    "split": split,
                    "relevant_ids": [],
                }
            )
    return turns, cases


def history_metrics(cases: list[Row], ranks: dict[str, list[str]]) -> Row:
    expected = sum(len(case["relevant_ids"]) for case in cases)
    found = sum(len(set(case["relevant_ids"]) & set(ranks[case["id"]][:5])) for case in cases)
    negatives = [case for case in cases if not case["relevant_ids"]]
    false_candidates = sum(bool(ranks[case["id"]]) for case in negatives)
    return {
        "expected_labels": expected,
        "found_at_5": found,
        "recall_at_5": found / expected if expected else None,
        "negative_queries": len(negatives),
        "negative_queries_with_candidates": false_candidates,
        "false_candidate_rate": false_candidates / len(negatives) if negatives else None,
    }


@dataclass
class EvaluationContext:
    settings: ResearchSettings
    ledger: EvaluationLedger
    model: BaseChatModel
    report: Row
    output: Path

    def save(self) -> None:
        self.report["usage"] = self.ledger.report()
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(self.report, ensure_ascii=False, indent=2) + "\n")
