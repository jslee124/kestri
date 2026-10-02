"""Synthetic history collection using production adapters."""

import hashlib
import json

import httpx

from kestri.agent.budget import Budget
from kestri.errors import PolicyDenied
from kestri.history.semantic import RECIPE, encode_turn
from kestri.integrations.embedding import EmbeddingClient, cosine_similarity
from kestri.memory.embedding import charged_embedding
from kestri.memory.retriever import lexical_rank, reciprocal_rank_fusion
from kestri.storage.store import Row
from scripts.evaluate_memory import THRESHOLDS
from scripts.memory_evaluation.common import (
    EvaluationContext,
    EvaluationControl,
    history_corpus,
    history_metrics,
)


async def run(context: EvaluationContext) -> None:
    settings, ledger = context.settings, context.ledger
    report, save = context.report, context.save
    config = settings.embedding_config()
    if config is None:
        raise PolicyDenied("EmbeddingNotConfigured")
    turns, cases = history_corpus()
    texts = [encode_turn(turn) for turn in turns] + [case["query"] for case in cases]
    report["corpus_sha256"] = hashlib.sha256(
        json.dumps({"texts": texts, "cases": cases}, ensure_ascii=False).encode()
    ).hexdigest()
    report.update(recipe=RECIPE, turn_count=len(turns), case_count=len(cases))
    vectors: list[tuple[float, ...]] = []
    async with httpx.AsyncClient(
        timeout=config.embedding_timeout_seconds, follow_redirects=False
    ) as http:
        client = EmbeddingClient(config, http)
        budget = Budget(settings, EvaluationControl(ledger))
        for offset in range(0, len(texts), 10):
            embedding_batch = await charged_embedding(
                client, texts[offset : offset + 10], budget, "history_evaluation", recipe=RECIPE
            )
            vectors.extend(embedding_batch.vectors)
            save()
    scores = {
        case["id"]: {
            turn["id"]: cosine_similarity(vectors[index], vectors[len(turns) + query_index])
            for index, turn in enumerate(turns)
        }
        for query_index, case in enumerate(cases)
    }
    calibration: list[Row] = []
    for threshold in THRESHOLDS:
        dense = {
            case["id"]: sorted(
                [turn for turn in turns if scores[case["id"]][turn["id"]] >= threshold],
                key=lambda turn: (-scores[case["id"]][turn["id"]], turn["id"]),
            )[:20]
            for case in cases
        }
        rankings = {
            case["id"]: [
                turn["id"]
                for turn in reciprocal_rank_fusion(
                    lexical_rank(turns, case["query"]), dense[case["id"]]
                )[:5]
            ]
            for case in cases
        }
        dense_rankings = {key: [turn["id"] for turn in value[:5]] for key, value in dense.items()}
        calibration.append(
            {
                "threshold": threshold,
                **{
                    split: {
                        "dense": history_metrics(
                            [case for case in cases if case["split"] == split], dense_rankings
                        ),
                        "hybrid": history_metrics(
                            [case for case in cases if case["split"] == split], rankings
                        ),
                    }
                    for split in ("development", "holdout")
                },
            }
        )
    eligible = [row for row in calibration if row["development"]["dense"]["recall_at_5"] >= 0.9]
    recommendation = min(
        eligible,
        key=lambda row: (
            row["development"]["dense"]["false_candidate_rate"],
            -row["threshold"],
        ),
        default=None,
    )
    report["development_recommendation"] = recommendation["threshold"] if recommendation else None
    report["metrics"] = calibration
    report["results"] = {"cosines": scores, "cases": cases}
