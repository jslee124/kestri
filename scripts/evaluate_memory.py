"""Reproducible synthetic candidate evaluation; never reads a database or owner chats."""

import argparse
import asyncio
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from kestri.errors import PolicyDenied, ProviderFailure
from kestri.integrations.embedding import EmbeddingClient, cosine_similarity
from kestri.memory.embedding import embedding_space
from kestri.memory.retriever import LEXICAL_VERSION, lexical_rank, reciprocal_rank_fusion
from kestri.settings import EmbeddingSettings

CORPUS = Path(__file__).resolve().parents[1] / "evals/memory/chinese-retrieval-v1.json"
SCORER = "eligible-fact-candidates-recall8-v1"
THRESHOLDS = [round(step / 100, 2) for step in range(20, 81, 5)]


def load_corpus(path: Path = CORPUS) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    corpus = json.loads(raw)
    facts, cases = corpus["facts"], corpus["cases"]
    identities = {fact["id"] for fact in facts}
    if len(identities) != len(facts) or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("DuplicateCorpusID")
    if len(cases) < 100 or len({case["category"] for case in cases}) < 8:
        raise ValueError("IncompleteCorpus")
    for case in cases:
        if case["split"] not in {"development", "holdout"}:
            raise ValueError("InvalidCorpusSplit")
        if not set(case["relevant_ids"]) <= identities:
            raise ValueError("UnknownCorpusLabel")
    texts = [fact["content"] for fact in facts] + [case["query"] for case in cases]
    if any(not text.strip() or len(text.encode()) > 8192 for text in texts):
        raise ValueError("InvalidCorpusText")
    return corpus, hashlib.sha256(raw).hexdigest()


def summarize(cases: list[dict[str, Any]], ranks: dict[str, list[str]]) -> dict[str, Any]:
    positives = [case for case in cases if case["relevant_ids"]]
    negatives = [case for case in cases if not case["relevant_ids"]]
    expected = sum(len(case["relevant_ids"]) for case in positives)
    found = sum(len(set(case["relevant_ids"]) & set(ranks[case["id"]][:8])) for case in positives)
    false_candidates = sum(bool(ranks[case["id"]]) for case in negatives)
    return {
        "relevant_labels": expected,
        "retrieved_relevant_at_8": found,
        "recall_at_8": found / expected if expected else None,
        "negative_queries": len(negatives),
        "negative_queries_with_candidates": false_candidates,
        "false_candidate_rate": false_candidates / len(negatives) if negatives else None,
    }


def score(corpus: dict[str, Any], vectors: list[tuple[float, ...]] | None) -> dict[str, Any]:
    facts, cases = corpus["facts"], corpus["cases"]
    lexical = {case["id"]: lexical_rank(facts, case["query"]) for case in cases}
    lexical_ids = {identity: [row["id"] for row in rows[:8]] for identity, rows in lexical.items()}
    result: dict[str, Any] = {
        "lexical": {
            split: summarize([case for case in cases if case["split"] == split], lexical_ids)
            for split in ("development", "holdout")
        },
    }
    if vectors is None:
        return result
    if len(vectors) != len(facts) + len(cases):
        raise ValueError("VectorCountMismatch")
    similarities = {
        case["id"]: sorted(
            [
                (cosine_similarity(vectors[index], vectors[len(facts) + query_index]), fact)
                for index, fact in enumerate(facts)
            ],
            key=lambda item: (-item[0], item[1]["id"]),
        )
        for query_index, case in enumerate(cases)
    }
    result["thresholds"] = []
    for threshold in THRESHOLDS:
        dense = {
            identity: [row for similarity, row in ranking if similarity >= threshold][:20]
            for identity, ranking in similarities.items()
        }
        hybrid = {
            identity: [row["id"] for row in reciprocal_rank_fusion(lexical[identity], rows)[:8]]
            for identity, rows in dense.items()
        }
        dense_ids = {identity: [row["id"] for row in rows[:8]] for identity, rows in dense.items()}
        result["thresholds"].append(
            {
                "threshold": threshold,
                **{
                    split: {
                        "dense": summarize(
                            [case for case in cases if case["split"] == split], dense_ids
                        ),
                        "hybrid": summarize(
                            [case for case in cases if case["split"] == split], hybrid
                        ),
                    }
                    for split in ("development", "holdout")
                },
            }
        )
    # Pick on development only; holdout must never influence the recommendation.
    eligible = [
        item for item in result["thresholds"] if item["development"]["dense"]["recall_at_8"] >= 0.9
    ]
    recommended = min(
        eligible,
        key=lambda item: (
            item["development"]["dense"]["false_candidate_rate"],
            -item["threshold"],
        ),
        default=None,
    )
    result["development_recommendation"] = recommended["threshold"] if recommended else None
    result["cases"] = [
        {
            "id": case["id"],
            "lexical_top8": lexical_ids[case["id"]],
            "similarities": {
                row["id"]: round(similarity, 6) for similarity, row in similarities[case["id"]]
            },
        }
        for case in cases
    ]
    return result


async def evaluate(live: bool, max_cost_usd: Decimal) -> dict[str, Any]:
    corpus, digest = load_corpus()
    evidence: dict[str, Any] = {
        "checked_at": datetime.now(UTC).isoformat(),
        "corpus_version": corpus["version"],
        "corpus_sha256": digest,
        "scorer_version": SCORER,
        "lexical_version": LEXICAL_VERSION,
        "scope": corpus["scope"],
        "label_source": corpus["label_source"],
        "case_count": len(corpus["cases"]),
        "categories": dict(Counter(case["category"] for case in corpus["cases"])),
        "mode": "live_embeddings" if live else "offline_lexical",
        "limits": [
            "single-author synthetic labels",
            "same facts across query splits",
            "candidate errors are not final injection errors",
            "no extraction, selector, database, history, Telegram or restart acceptance",
        ],
    }
    vectors: list[tuple[float, ...]] | None = None
    if live:
        settings = EmbeddingSettings()
        if settings.embedding_dimensions != 1024:
            raise PolicyDenied("EvaluationDimensions")
        texts = [fact["content"] for fact in corpus["facts"]]
        texts += [case["query"] for case in corpus["cases"]]
        # Worst-case admission estimate: UTF-8 bytes as token upper bound, configured rates.
        # This standalone synthetic run has no product ledger and no automatic retries.
        rate = Decimal("0.5") * Decimal("0.15") / 1_000_000
        reservation = sum(len(text.encode()) for text in texts) * rate
        if reservation > max_cost_usd:
            raise PolicyDenied("EvaluationBudgetExceeded")
        vectors = []
        requests = tokens = 0
        async with httpx.AsyncClient(
            timeout=settings.embedding_timeout_seconds, follow_redirects=False
        ) as http:
            client = EmbeddingClient(settings, http)
            for offset in range(0, len(texts), 10):
                batch = await client.embed(texts[offset : offset + 10])
                vectors.extend(batch.vectors)
                requests += 1
                tokens += batch.input_tokens
        evidence["provider"] = {
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
            "embedding_space": embedding_space(settings),
            "region": "cn-beijing",
            "requests": requests,
            "input_tokens": tokens,
            "estimated_cost_usd": str(tokens * rate),
            "reserved_upper_estimate_usd": str(reservation),
            "cost_basis": "0.5 CNY/million tokens, fixed 0.15 USD/CNY; not an invoice",
        }
    evidence["metrics"] = score(corpus, vectors)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Send only the fixed synthetic corpus")
    parser.add_argument("--max-cost-usd", type=Decimal, default=Decimal("0.02"))
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if not arguments.max_cost_usd.is_finite() or not 0 < arguments.max_cost_usd <= Decimal("0.02"):
        parser.error("cost bound must be positive and at most USD 0.02")
    try:
        evidence = asyncio.run(evaluate(arguments.live, arguments.max_cost_usd))
    except PolicyDenied, ProviderFailure, ValidationError, httpx.HTTPError:
        print("Evaluation failed; no provider body or configuration printed.", file=sys.stderr)
        return 1
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in evidence.items() if key != "metrics"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
