"""Versioned embedding space and audited CNY-to-USD accounting for product requests."""

import asyncio
import hashlib
import json
import math
from decimal import ROUND_CEILING

from psycopg.types.json import Jsonb

from kestri.budget import Budget
from kestri.embedding import EmbeddingBatch, EmbeddingClient
from kestri.errors import PolicyDenied, ProviderFailure
from kestri.memory_extractor import SECRET_PATTERN
from kestri.settings import EmbeddingSettings


def embedding_space(settings: EmbeddingSettings) -> str:
    recipe = [
        "dashscope",
        "cn-beijing",
        settings.embedding_base_url,
        settings.embedding_model,
        settings.embedding_dimensions,
        "compatible-float-symmetric-l2-v1",
    ]
    return "dashscope-v1-" + hashlib.sha256(json.dumps(recipe).encode()).hexdigest()


def content_hash(text: str) -> str:
    # Content fingerprint for stale-index exclusion, not authentication of external data.
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


def vector_literal(values: tuple[float, ...]) -> str:
    norm = math.hypot(*values)
    if (
        len(values) != 1024
        or not all(math.isfinite(v) for v in values)
        or not math.isfinite(norm)
        or norm == 0
    ):
        raise PolicyDenied("InvalidIndexVector")
    # Cosine is scale-invariant; normalization avoids float32 overflow/zero underflow.
    return "[" + ",".join(str(v / norm) for v in values) + "]"


async def charged_embedding(
    client: EmbeddingClient, texts: list[str], budget: Budget, kind: str
) -> EmbeddingBatch:
    if not 1 <= len(texts) <= 10 or any(not t.strip() or len(t.encode()) > 8192 for t in texts):
        raise PolicyDenied("EmbeddingInputLimit")
    if any(budget.control.store.redactor.text(t) != t or SECRET_PATTERN.search(t) for t in texts):
        raise PolicyDenied("MemoryEmbeddingSecret")
    tokens_bound = sum(len(t.encode()) + 256 for t in texts)
    rate = budget.settings.embedding_cny_per_million
    conversion = budget.settings.embedding_usd_per_cny

    def cost(tokens: int) -> int:
        return max(1, int((tokens * rate * conversion).to_integral_value(rounding=ROUND_CEILING)))

    metadata = {
        "provider": "dashscope",
        "space": embedding_space(client.settings),
        "original_currency": "CNY",
        "cny_per_million": str(rate),
        "usd_per_cny": str(conversion),
        "conversion_version": budget.settings.embedding_conversion_version,
        "estimated_cny": str(tokens_bound * rate / 1_000_000),
    }
    reservation = await budget.reserve(kind, cost(tokens_bound))
    await budget.control.store.execute(
        "UPDATE kestri.usage SET metadata=%s WHERE id=%s", (Jsonb(metadata), reservation)
    )
    try:
        await budget.control.ensure_active()
        async with asyncio.timeout(client.settings.embedding_timeout_seconds):
            result = await client.embed(texts)
        if result.input_tokens > tokens_bound:
            raise ProviderFailure("EmbeddingUsageOutOfBounds")
        await budget.control.store.settle(
            reservation,
            {
                **metadata,
                "input_tokens": result.input_tokens,
                "total_tokens": result.total_tokens,
                "original_cny": str(result.input_tokens * rate / 1_000_000),
            },
            cost(result.input_tokens),
        )
        await budget.control.ensure_active()
        return result
    except BaseException:
        await budget.control.store.execute(
            "UPDATE kestri.usage SET state='unknown' WHERE id=%s AND state='reserved'",
            (reservation,),
        )
        raise
