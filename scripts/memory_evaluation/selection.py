"""Synthetic selection collection using production adapters."""

import asyncio
import hashlib
import json
from typing import cast
from uuid import NAMESPACE_URL, uuid5

from kestri.agent.budget import Budget
from kestri.errors import BudgetExceeded
from kestri.memory.retriever import MemoryRetriever, lexical_rank
from kestri.storage.store import Store
from scripts.evaluate_memory import load_corpus
from scripts.memory_evaluation.common import (
    EMBEDDINGS,
    EvaluationContext,
    EvaluationControl,
    selection_candidates,
    selection_metrics,
)


async def run(context: EvaluationContext) -> None:
    settings, ledger, model = context.settings, context.ledger, context.model
    report, save = context.report, context.save
    corpus, digest = load_corpus()
    evidence = json.loads(EMBEDDINGS.read_text())
    if evidence["corpus_sha256"] != digest:
        raise ValueError("EmbeddingEvidenceCorpusMismatch")
    report.update(
        corpus_sha256=digest, corpus_version=corpus["version"], case_count=len(corpus["cases"])
    )
    candidates = selection_candidates(corpus, evidence, settings.memory_dense_min_similarity)
    identities = {fact["id"]: uuid5(NAMESPACE_URL, fact["id"]) for fact in corpus["facts"]}
    originals = {str(value): key for key, value in identities.items()}
    all_rows = [
        {
            **fact,
            "id": identities[fact["id"]],
            "category": "background",
            "task_id": None,
            "origin": "auto_direct",
            "expires_at": None,
            "review_after": None,
        }
        for fact in corpus["facts"]
    ]
    for case in corpus["cases"]:
        budget = Budget(settings, EvaluationControl(ledger))
        retriever = MemoryRetriever(cast(Store, ledger), budget, model, None)
        rows = [
            {
                **row,
                "id": identities[row["id"]],
                "category": "background",
                "task_id": None,
                "origin": "auto_direct",
                "expires_at": None,
                "review_after": None,
            }
            for row in candidates[case["id"]]
        ]
        error = None
        try:
            async with asyncio.timeout(settings.memory_retrieval_timeout_seconds):
                selected = await retriever.select(case["query"], rows)
        except BudgetExceeded:
            save()
            raise
        except Exception as failure:
            # Production fallback is lexical, not empty; count its errors honestly.
            error = type(failure).__name__
            selected = lexical_rank(all_rows, case["query"])[:8]
        selected = retriever.assemble(all_rows, selected)
        report["results"][case["id"]] = {
            "selected_ids": [originals[str(row["id"])] for row in selected],
            "error": error,
        }
        save()
        if len(report["results"]) % 10 == 0:
            print(f"selection: {len(report['results'])}/{report['case_count']}", flush=True)
    report["threshold"] = settings.memory_dense_min_similarity
    report["embedding_evidence_sha256"] = hashlib.sha256(EMBEDDINGS.read_bytes()).hexdigest()
    report["metrics"] = {
        split: selection_metrics(
            [case for case in corpus["cases"] if case["split"] == split], report["results"]
        )
        for split in ("development", "holdout")
    }
