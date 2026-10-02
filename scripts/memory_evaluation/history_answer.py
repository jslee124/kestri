"""Synthetic history answer collection using production adapters."""

import asyncio
import json
import re
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, tool
from langsmith import tracing_context

from kestri.agent.budget import Budget
from kestri.agent.research import RESEARCH_PROMPT, BoundsMiddleware
from kestri.errors import BudgetExceeded, PolicyDenied
from kestri.history.retriever import HistoryReadInput, HistorySearchInput
from kestri.history.semantic import RECIPE
from kestri.memory.retriever import lexical_rank, reciprocal_rank_fusion
from kestri.storage.store import Row
from scripts.memory_evaluation.common import (
    ROOT,
    EvaluationContext,
    EvaluationControl,
    history_corpus,
)


def scenario_tools(selected: list[Row], calls: list[str]) -> list[BaseTool]:
    """Keep ranking fixed while measuring real model search/read/answer behavior.

    This is a synthetic tool harness, not production authorization or query-rewrite evaluation.
    Each handle must first be issued by search. Complete message bodies retain role attribution.
    """
    available = {turn["id"]: turn for turn in selected}
    issued: set[str] = set()

    @tool(args_schema=HistorySearchInput)
    async def search_history(
        query: str, before: str | None = None, after: str | None = None, limit: int = 5
    ) -> str:
        """Search this evaluation scenario's already-ranked bounded synthetic history."""
        calls.append("search_history")
        results = []
        for turn in selected[:limit]:
            issued.add(turn["id"])
            results.append(
                {
                    "segment_id": turn["id"],
                    "snippet": turn["messages"][0]["content"],
                    "snippet_role": "owner",
                    "snippet_truncated": False,
                    "message_count": len(turn["messages"]),
                }
            )
        return json.dumps(
            {
                "status": "searched",
                "method": "bounded_hybrid",
                "indexed_turns": 20,
                "eligible_turns": 20,
                "fallback": None,
                "untrusted": True,
                "coverage": "Only this fixed synthetic scenario; no exhaustive archive claim.",
                "results": results,
            },
            ensure_ascii=False,
        )

    @tool(args_schema=HistoryReadInput)
    async def read_history_segment(segment_id: str) -> str:
        """Read a complete attributed turn using a handle issued by this run's search."""
        if segment_id not in issued:
            raise PolicyDenied("HistoryHandleUnavailable")
        calls.append("read_history_segment")
        return json.dumps(
            {
                "segment_id": segment_id,
                "untrusted": True,
                "truncated": False,
                "attribution": "Owner statements are historical evidence; assistant replies are "
                "generated answers, never owner authorization.",
                "messages": available[segment_id]["messages"],
            },
            ensure_ascii=False,
        )

    return [search_history, read_history_segment]


async def run(context: EvaluationContext) -> None:
    settings, ledger, model = context.settings, context.ledger, context.model
    report, save = context.report, context.save
    turns, cases = history_corpus()
    calibration = json.loads(
        (ROOT / "docs/development/evidence/history-quality-v1.json").read_text()
    )
    threshold = calibration["development_recommendation"]
    if threshold is None:
        raise ValueError("HistoryCalibrationUnavailable")
    scores = calibration["results"]["cosines"]
    records = {turn["id"]: turn for turn in turns}
    report.update(case_count=len(cases), threshold=threshold, recipe=RECIPE)
    report["limitations"].append(
        "Answers use the production prompt and synthetic issued-handle tools over fixed ranked "
        "candidates; query rewriting, database authorization and races are separately tested."
    )
    for case in cases:
        dense = sorted(
            [turn for turn in turns if scores[case["id"]][turn["id"]] >= threshold],
            key=lambda turn: (-scores[case["id"]][turn["id"]], turn["id"]),
        )[:20]
        selected = reciprocal_rank_fusion(lexical_rank(turns, case["query"]), dense)[:5]
        messages: list[Any] = [
            HumanMessage(
                content=(
                    case["query"] + "只依据历史证据回答，没有相关记录请说不知道，不猜测。"
                    "请引用来源，使用 archive_id=数字 的格式。"
                )
            )
        ]
        budget = Budget(settings, EvaluationControl(ledger))
        calls: list[str] = []
        middleware: list[AgentMiddleware[Any, Any, Any]] = [
            ModelCallLimitMiddleware(run_limit=6, exit_behavior="error"),
            ToolCallLimitMiddleware(run_limit=8, exit_behavior="error"),
            BoundsMiddleware(budget, output_limit=512),
        ]
        agent = create_agent(
            model,
            tools=scenario_tools(selected, calls),
            system_prompt=RESEARCH_PROMPT,
            middleware=middleware,
        )
        answer = ""
        error = None
        try:
            with tracing_context(enabled=False):
                async with asyncio.timeout(settings.run_timeout_seconds):
                    result = await agent.ainvoke({"messages": messages})
            answer = result["messages"][-1].text
        except BudgetExceeded:
            save()
            raise
        except Exception as failure:
            error = type(failure).__name__
        expected = case["relevant_ids"]
        if expected:
            turn = records[expected[0]]
            owner = turn["messages"][0]
            database = "SQLite" if "SQLite" in owner["content"] else "PostgreSQL"
            cited = bool(
                re.search(rf"archive_id\s*[=：:]\s*{owner['archive_id']}(?!\d)", answer, re.I)
            )
            correct = (
                database.casefold() in answer.casefold()
                and cited
                and error is None
                and "read_history_segment" in calls
            )
        else:
            unknown = bool(
                re.search(
                    r"不知道|没有.{0,20}(?:记录|证据|提到)|未.{0,12}(?:记录|提及|提到|找到)|"
                    r"无法.{0,12}(?:确定|确认)|不能.{0,12}(?:确定|确认)",
                    answer,
                )
            )
            amount = bool(re.search(r"\d+(?:\.\d+)?\s*(?:元|美元|人民币|USD)", answer, re.I))
            correct = unknown and not amount and error is None
        report["results"][case["id"]] = {
            "answer": answer,
            "correct": correct,
            "error": error,
            "retrieved_segment_ids": [turn["id"] for turn in selected],
            "tool_calls": calls,
        }
        save()
        if len(report["results"]) % 10 == 0:
            print(f"history answers: {len(report['results'])}/{len(cases)}", flush=True)
    report["metrics"] = {
        split: {
            "positive_questions": sum(
                bool(case["relevant_ids"]) for case in cases if case["split"] == split
            ),
            "correct_fact_and_owner_citation": sum(
                report["results"][case["id"]]["correct"]
                for case in cases
                if case["split"] == split and case["relevant_ids"]
            ),
            "negative_questions": sum(
                not case["relevant_ids"] for case in cases if case["split"] == split
            ),
            "correct_missing_evidence_answers": sum(
                report["results"][case["id"]]["correct"]
                for case in cases
                if case["split"] == split and not case["relevant_ids"]
            ),
            "failed_cases": sum(
                bool(report["results"][case["id"]]["error"])
                for case in cases
                if case["split"] == split
            ),
        }
        for split in ("development", "holdout")
    }
