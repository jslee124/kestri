"""Bounded on-demand derived history vectors; exact search and revocable cache writes."""

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from psycopg import AsyncConnection

from kestri.errors import PolicyDenied
from kestri.integrations.embedding import EmbeddingClient
from kestri.memory.embedding import charged_embedding, embedding_space, vector_literal
from kestri.storage.store import Row

if TYPE_CHECKING:
    from kestri.history.retriever import HistoryRetriever

RECIPE = "history-complete-messages-json-v1"


def history_space(client: EmbeddingClient) -> str:
    return (
        "history-v1-"
        + hashlib.sha256((embedding_space(client.settings) + RECIPE).encode()).hexdigest()
    )


def encode_turn(row: Row) -> str:
    return json.dumps(row["messages"], ensure_ascii=False, separators=(",", ":"))


class HistorySemantic:
    def __init__(self, history: HistoryRetriever, client: EmbeddingClient) -> None:
        self.history, self.client = history, client
        self.queries: dict[str, tuple[float, ...]] = {}
        self.attempts = 0
        self.index_attempted = False

    async def publish(
        self,
        state: Row,
        rows: list[Row],
        vectors: list[tuple[float, ...]],
        *,
        guard: Callable[[AsyncConnection[Row]], Awaitable[None]] | None = None,
        complete: Callable[[AsyncConnection[Row]], Awaitable[None]] | None = None,
    ) -> None:
        history = self.history
        async with history.store.pool.connection() as conn:
            async with conn.transaction():
                current = await (
                    await conn.execute(
                        "SELECT * FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                        (history.run["chat_id"],),
                    )
                ).fetchone()
                if (
                    not current
                    or history.version(current) != history.version(state)
                    or not all(
                        current[k] == state[k]
                        for k in (
                            "memory_use_enabled",
                            "auto_memory_enabled",
                            "memory_semantic_enabled",
                            "memory_embedding_space",
                            "memory_retrieval_generation",
                        )
                    )
                ):
                    raise PolicyDenied("HistoryIndexSettingsChanged")
                if guard is not None:
                    await guard(conn)
                # Source operations lock/delete these same rows or reset the owner epoch.
                for item, vector in zip(rows, vectors, strict=True):
                    sources = await (
                        await conn.execute(
                            "SELECT id FROM kestri.messages WHERE chat_id=%s AND run_id="
                            "(SELECT run_id FROM kestri.messages WHERE id=%s) "
                            "ORDER BY id FOR UPDATE",
                            (history.run["chat_id"], item["owner_id"]),
                        )
                    ).fetchall()
                    if not sources:
                        if guard is not None:
                            raise PolicyDenied("HistorySourceChanged")
                        continue
                    fresh = await history.turns(state, None, None, item["owner_id"], conn=conn)
                    if not fresh or fresh[0]["id"] != item["id"]:
                        if guard is not None:
                            raise PolicyDenied("HistorySourceChanged")
                        continue
                    await conn.execute(
                        "INSERT INTO kestri.history_embeddings("
                        "owner_message_id,chat_id,source_hash,"
                        "embedding_space,settings_generation,retrieval_generation,embedding) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s::public.vector) ON CONFLICT "
                        "(owner_message_id,embedding_space) DO UPDATE SET "
                        "source_hash=EXCLUDED.source_hash,"
                        "settings_generation=EXCLUDED.settings_generation,"
                        "retrieval_generation=EXCLUDED.retrieval_generation,"
                        "embedding=EXCLUDED.embedding,created_at=now()",
                        (
                            item["owner_id"],
                            history.run["chat_id"],
                            item["id"],
                            history_space(self.client),
                            state["memory_settings_generation"],
                            state["memory_retrieval_generation"],
                            vector_literal(vector),
                        ),
                    )

                if complete is not None:
                    await complete(conn)

    async def rank(self, state: Row, rows: list[Row], query: str) -> tuple[list[Row], int]:
        history = self.history
        ready = await history.store.one("SELECT to_regclass('kestri.history_embeddings') AS name")
        if not ready or not ready["name"] or not rows:
            return [], 0
        allowed = {r["owner_id"]: r for r in rows}
        cached = await history.store.all(
            "SELECT owner_message_id,source_hash FROM kestri.history_embeddings "
            "WHERE chat_id=%s AND embedding_space=%s AND settings_generation=%s "
            "AND retrieval_generation=%s AND owner_message_id=ANY(%s)",
            (
                history.run["chat_id"],
                history_space(self.client),
                state["memory_settings_generation"],
                state["memory_retrieval_generation"],
                list(allowed),
            ),
        )
        valid = {
            r["owner_message_id"]
            for r in cached
            if allowed[r["owner_message_id"]]["id"] == r["source_hash"]
        }
        missing: list[Row] = []
        if not self.index_attempted:
            self.index_attempted = True
            missing = [
                r
                for r in rows
                if r["owner_id"] not in valid and len(encode_turn(r).encode()) <= 8192
            ][:9]
        if not valid and not missing:
            return [], 0
        if query not in self.queries:
            if self.attempts >= 3:
                raise PolicyDenied("HistoryQueryLimit")
            self.attempts += 1
            async with asyncio.timeout(history.budget.settings.memory_retrieval_timeout_seconds):
                result = await charged_embedding(
                    self.client,
                    [query, *[encode_turn(r) for r in missing]],
                    history.budget,
                    "history_retrieval",
                    recipe=RECIPE,
                )
                await history.recheck(state)
                await self.publish(state, missing, list(result.vectors[1:]))
                self.queries[query] = result.vectors[0]
        vector = vector_literal(self.queries[query])
        matches = await history.store.all(
            "SELECT owner_message_id,source_hash,1-(embedding OPERATOR(public.<=>) "
            "%s::public.vector) AS similarity FROM kestri.history_embeddings "
            "WHERE chat_id=%s AND embedding_space=%s AND settings_generation=%s "
            "AND retrieval_generation=%s AND owner_message_id=ANY(%s) "
            "ORDER BY embedding OPERATOR(public.<=>) %s::public.vector,owner_message_id LIMIT 200",
            (
                vector,
                history.run["chat_id"],
                history_space(self.client),
                state["memory_settings_generation"],
                state["memory_retrieval_generation"],
                list(allowed),
                vector,
            ),
        )
        eligible = [r for r in matches if allowed[r["owner_message_id"]]["id"] == r["source_hash"]]
        dense = [
            allowed[r["owner_message_id"]]
            for r in eligible
            if r["similarity"] >= history.budget.settings.memory_dense_min_similarity
        ][:20]
        return dense, len(eligible)
