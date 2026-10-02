"""Bounded Beijing embedding adapter and public-text connection check."""

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from kestri.errors import PolicyDenied, ProviderFailure
from kestri.integrations.http import post_json
from kestri.settings import EmbeddingSettings


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: tuple[tuple[float, ...], ...]
    input_tokens: int
    total_tokens: int


class EmbeddingClient:
    """Caller owns the HTTP client, including its configured request timeout."""

    def __init__(self, settings: EmbeddingSettings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        # UTF-8 bytes are a conservative local admission bound, not a provider tokenizer.
        if not 1 <= len(texts) <= 10 or any(
            not text.strip() or len(text.encode("utf-8")) > 8192 for text in texts
        ):
            raise PolicyDenied("EmbeddingInputLimit")
        if any(self.settings.dashscope_api_key.get_secret_value() in text for text in texts):
            raise PolicyDenied("EmbeddingSecretInput")
        try:
            body = await post_json(
                self.client,
                self.settings.embedding_base_url + "/embeddings",
                {
                    "model": self.settings.embedding_model,
                    "input": texts,
                    "dimensions": self.settings.embedding_dimensions,
                    "encoding_format": "float",
                },
                headers={
                    "Authorization": "Bearer " + self.settings.dashscope_api_key.get_secret_value()
                },
                max_bytes=2_000_000,
            )
        except httpx.HTTPError:
            raise ProviderFailure("EmbeddingTransportFailure") from None
        data = body.get("data")
        usage = body.get("usage")
        if (
            body.get("model") != self.settings.embedding_model
            or not isinstance(data, list)
            or len(data) != len(texts)
            or not isinstance(usage, dict)
        ):
            raise ProviderFailure("InvalidEmbeddingResponse")
        ordered: dict[int, tuple[float, ...]] = {}
        for item in data:
            if not isinstance(item, dict):
                raise ProviderFailure("InvalidEmbeddingResponse")
            index = item.get("index")
            vector = item.get("embedding")
            if (
                type(index) is not int
                or not 0 <= index < len(texts)
                or index in ordered
                or not isinstance(vector, list)
                or len(vector) != self.settings.embedding_dimensions
                or any(type(value) not in {int, float} for value in vector)
            ):
                raise ProviderFailure("InvalidEmbeddingVector")
            try:
                values = tuple(float(value) for value in vector)
            except OverflowError, ValueError:
                raise ProviderFailure("InvalidEmbeddingVector") from None
            norm = math.hypot(*values)
            if (
                any(not math.isfinite(value) for value in values)
                or not math.isfinite(norm)
                or norm == 0
            ):
                raise ProviderFailure("InvalidEmbeddingVector")
            ordered[index] = values
        input_tokens = usage.get("prompt_tokens")
        total_tokens = usage.get("total_tokens")
        if (
            type(input_tokens) is not int
            or type(total_tokens) is not int
            or input_tokens < 0
            or total_tokens < input_tokens
        ):
            raise ProviderFailure("InvalidEmbeddingUsage")
        return EmbeddingBatch(
            tuple(ordered[index] for index in range(len(texts))), input_tokens, total_tokens
        )


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        math.hypot(*left) * math.hypot(*right)
    )


async def run_embedding_smoke(settings: EmbeddingSettings) -> dict[str, Any]:
    # Exactly one request, three fixed texts; never inspect owner messages or database.
    async with httpx.AsyncClient(
        timeout=settings.embedding_timeout_seconds, follow_redirects=False
    ) as http:
        batch = await EmbeddingClient(settings, http).embed(
            [
                "我希望这个项目能体现智能体工程能力，帮助我找工作。",
                "怎样把这个作品做得更适合求职，展示 agent 开发水平？",
                "今天的晚餐是西红柿炒鸡蛋和米饭。",
            ]
        )
    related = cosine_similarity(batch.vectors[0], batch.vectors[1])
    unrelated = cosine_similarity(batch.vectors[0], batch.vectors[2])
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "provider": "dashscope",
        "region": "cn-beijing",
        "model": settings.embedding_model,
        "dimensions": settings.embedding_dimensions,
        "requests": 1,
        "vectors": len(batch.vectors),
        "input_tokens": batch.input_tokens,
        "total_tokens": batch.total_tokens,
        "related_similarity": round(related, 6),
        "unrelated_similarity": round(unrelated, 6),
        "passed": related > unrelated,
        "scope": "connection, vector validation, and one fixed semantic comparison only",
    }


def save_embedding_evidence(settings: EmbeddingSettings, evidence: dict[str, Any]) -> Path:
    settings.embedding_evidence_dir.mkdir(parents=True, exist_ok=True)
    path = settings.embedding_evidence_dir / f"embedding-{uuid4()}.json"
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    return path
