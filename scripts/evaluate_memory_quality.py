"""Live synthetic memory quality collectors; no database, private archive or Telegram access."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from kestri.agent.runtime import build_model
from kestri.redaction import Redactor
from kestri.settings import ResearchSettings
from kestri.storage.store import Row
from scripts.memory_evaluation import extraction, history, history_answer, selection
from scripts.memory_evaluation.common import SCORER, EvaluationContext, EvaluationLedger


async def evaluate(stage: str, cap: Decimal, output: Path) -> Row:
    settings = ResearchSettings().model_copy(update={"max_output_tokens": 2048})
    redactor = Redactor([settings.deepseek_api_key.get_secret_value()])
    ledger = EvaluationLedger(cap, redactor)
    report: Row = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "stage": stage,
        "scorer": SCORER,
        "model": settings.model,
        "results": {},
        "metrics": {},
        "limitations": [
            "synthetic single-author labels; no independent human review",
            "no owner archive, database or Telegram access",
            "related injection is measured separately from always-present profile",
            "keyword/action extraction matching is conservative, not human semantic scoring",
        ],
    }
    context = EvaluationContext(settings, ledger, build_model(settings), report, output)
    stages = {
        "extraction": extraction.run,
        "selection": selection.run,
        "history": history.run,
        "history_answer": history_answer.run,
    }
    try:
        await stages[stage](context)
    finally:
        context.save()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=["extraction", "selection", "history", "history_answer"], required=True
    )
    parser.add_argument("--max-cost-usd", type=Decimal, default=Decimal("0.50"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.max_cost_usd.is_finite() or not 0 < args.max_cost_usd <= Decimal("0.50"):
        parser.error("evaluation cap must be positive and at most USD 0.50")
    try:
        report = asyncio.run(evaluate(args.stage, args.max_cost_usd, args.output))
    except Exception as failure:
        print(f"Evaluation stopped ({type(failure).__name__}); details suppressed.")
        return 1
    print(json.dumps({"stage": args.stage, "usage": report["usage"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
