"""Synthetic extraction collection using production adapters."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from kestri.agent.budget import Budget
from kestri.errors import BudgetExceeded, PolicyDenied
from kestri.memory.extractor import ExtractionBatch, MemoryExtractor, MemoryOperation
from kestri.memory.worker import SOURCE_ANNOTATION_RETRY_REASONS
from scripts.memory_evaluation.common import (
    EXTRACTION,
    EvaluationContext,
    EvaluationControl,
    extraction_metrics,
)


async def run(context: EvaluationContext) -> None:
    settings, ledger, model = context.settings, context.ledger, context.model
    report, save = context.report, context.save
    corpus = json.loads(EXTRACTION.read_text())
    report["corpus_sha256"] = hashlib.sha256(EXTRACTION.read_bytes()).hexdigest()
    report["corpus_version"] = corpus["version"]
    report["case_count"] = len(corpus["cases"])
    extractor = MemoryExtractor(model, ledger.redactor)
    for case in corpus["cases"]:
        created = datetime(2026, 10, 2, tzinfo=UTC)
        sources = [
            {
                "message_id": index + 1,
                "chat_id": 111,
                "role": "assistant",
                "provenance": "context",
                "text": text,
                "created_at": created,
                "fresh": False,
            }
            for index, text in enumerate(case["context"])
        ]
        sources.append(
            {
                "message_id": 17,
                "chat_id": 111,
                "role": "owner",
                "provenance": "direct",
                "text": case["source"],
                "created_at": created,
                "fresh": True,
            }
        )
        existing = []
        if case["existing"]:
            existing.append(
                {
                    "id": uuid5(NAMESPACE_URL, case["id"]),
                    "chat_id": 111,
                    "scope": "global",
                    "revision": 1,
                    "last_source_message_id": 1,
                    "origin": "auto_direct",
                    **case["existing"],
                }
            )
        batch = ExtractionBatch.model_validate(
            {
                "chat_id": 111,
                "memory_revision": 0,
                "memory_epoch": 0,
                "settings_generation": 0,
                "enabled": True,
                "activation_watermark": 0,
                "automatic_history_floor": 0,
                "sources": sources,
                "existing": existing,
            }
        )
        operations: list[MemoryOperation] = []
        error = None
        attempts = 0
        while attempts < 3:
            attempts += 1
            try:
                result = await extractor.extract(batch, Budget(settings, EvaluationControl(ledger)))
                operations = [op for op in result.operations if op.action != "candidate"]
                error = None
                break
            except BudgetExceeded:
                save()
                raise
            except Exception as failure:
                error = type(failure).__name__
                if (
                    not isinstance(failure, PolicyDenied)
                    or str(failure) not in SOURCE_ANNOTATION_RETRY_REASONS
                ):
                    break
        report["results"][case["id"]] = {
            "operations": [op.model_dump(mode="json") for op in operations],
            "error": error,
            "attempts": attempts,
        }
        save()
        if len(report["results"]) % 10 == 0:
            print(f"extraction: {len(report['results'])}/{report['case_count']}", flush=True)
    report["metrics"] = {
        split: extraction_metrics(
            [case for case in corpus["cases"] if case["split"] == split], report["results"]
        )
        for split in ("development", "holdout")
    }
