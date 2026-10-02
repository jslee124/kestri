import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from langchain_core.messages import HumanMessage

from kestri.budget import Budget, RunControl
from kestri.data import TABLES, DataService, read_private
from kestri.embedding import EmbeddingClient
from kestri.errors import BudgetExceeded, PolicyDenied
from kestri.memory import MemoryService
from kestri.memory_embedding import embedding_space
from kestri.memory_index import IndexBudget, IndexControl, MemoryIndexWorker
from kestri.memory_retriever import MemoryRetriever
from kestri.workspace import Workspace

from .helpers import (
    TEST_DSN,
    accept_memory_control_run,
    accept_run,
    model_tool_call,
    offline_model,
    research_settings,
    save_memory,
)

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="Set dedicated KESTRI_TEST_DATABASE_URL")
VECTOR = tuple([1.0] + [0.0] * 1023)
OTHER = tuple([0.0, 1.0] + [0.0] * 1022)


def configured(**overrides: Any) -> Any:
    return research_settings(
        DASHSCOPE_API_KEY="embedding-test-only",
        embedding_base_url="https://test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        **overrides,
    )


async def semantic(
    store: Any, identity: int = 50, mode: str = "semantic", enabled: bool = True
) -> None:
    store.embedding_space = embedding_space(configured().embedding_config())
    await store.accept(
        identity,
        111,
        identity,
        "/memory " + mode + " " + ("on" if enabled else "off"),
        None,
        "memory",
        8,
    )


@pytest.fixture
async def vector_store(store: Any) -> Any:
    ready = await store.one("SELECT to_regclass('kestri.memory_embeddings') AS name")
    if not ready["name"]:
        pytest.skip("This matrix leg has no pgvector; vector leg is required separately")
    return store


async def index_all(store: Any, vectors: dict[str, tuple[float, ...]] | None = None) -> None:
    async with httpx.AsyncClient() as http:
        worker = MemoryIndexWorker(
            store, configured(), EmbeddingClient(configured().embedding_config(), http)
        )
        while (job := await worker.claim(111)) is not None:
            await worker.publish(job, (vectors or {}).get(job["content"], VECTOR))


async def test_default_off_enqueue_index_once_and_version_invalidation(vector_store: Any) -> None:
    store = vector_store
    memory = await save_memory(store, "我在学习智能体系统")
    assert not await store.all("SELECT * FROM kestri.memory_index_jobs")
    await semantic(store)
    assert len(await store.all("SELECT * FROM kestri.memory_index_jobs")) == 1
    await index_all(store)
    await semantic(store, 51)
    assert len(await store.all("SELECT * FROM kestri.memory_index_jobs")) == 1
    assert (await store.one("SELECT vector_dims(embedding) AS n FROM kestri.memory_embeddings"))[
        "n"
    ] == 1024
    run = await accept_memory_control_run(
        store, "/correct " + str(memory["id"])[:8] + " 我正在学习英语", 2
    )
    await MemoryService(store, configured()).apply(run)
    await store.finish(run["id"], "completed", "saved")
    assert not await store.all(
        "SELECT * FROM kestri.memory_embeddings WHERE memory_id=%s", (memory["id"],)
    )
    assert len(await store.all("SELECT * FROM kestri.memory_index_jobs WHERE status='queued'")) == 1
    await store.open()
    assert (await store.one("SELECT max(version) AS n FROM kestri.migrations"))["n"] == 6


async def test_index_lease_reclaim_forget_and_closed_setting_guard(vector_store: Any) -> None:
    store = vector_store
    memory = await save_memory(store, "我在学习智能体系统")
    await semantic(store)
    async with httpx.AsyncClient() as http:
        worker = MemoryIndexWorker(
            store, configured(), EmbeddingClient(configured().embedding_config(), http)
        )
        claims = await asyncio.gather(worker.claim(111), worker.claim(111))
        old = next(j for j in claims if j)
        assert sum(j is not None for j in claims) == 1
        await store.execute(
            "UPDATE kestri.memory_index_jobs SET lease_until=now()-interval '1 second'"
        )
        new = await worker.claim(111)
        assert new["lease_token"] != old["lease_token"] and new["run_id"] == old["run_id"]
        with pytest.raises(PolicyDenied):
            await worker.publish(old, VECTOR)
        await worker.fail(old, "OldFailure")
        await worker.ensure_active(new)
        run = await accept_memory_control_run(store, "/forget " + str(memory["id"])[:8], 2)
        await MemoryService(store, configured()).apply(run)
        await store.finish(run["id"], "completed", "forgotten")
        with pytest.raises(PolicyDenied):
            await worker.publish(new, VECTOR)
        with pytest.raises(PolicyDenied):
            await IndexBudget(configured(), IndexControl(worker, new)).reserve("index", 10)
        assert not await store.all("SELECT * FROM kestri.memory_embeddings")
        assert (await store.one("SELECT status FROM kestri.runs WHERE id=%s", (new["run_id"],)))[
            "status"
        ] == "cancelled"


async def test_mock_embedding_index_cny_ledger_and_unknown_failure(vector_store: Any) -> None:
    store = vector_store
    await save_memory(store, "我在学习智能体系统")
    await semantic(store)
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-v4",
                "data": [{"index": 0, "embedding": list(VECTOR)}],
                "usage": {"prompt_tokens": 9, "total_tokens": 9},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        worker = MemoryIndexWorker(
            store, configured(), EmbeddingClient(configured().embedding_config(), http)
        )
        assert await worker.work_once(111)
    usage = await store.one("SELECT * FROM kestri.usage WHERE kind='memory_index'")
    assert usage["state"] == "recorded" and usage["amount_micro_usd"] == 1
    assert (
        usage["metadata"]["original_currency"] == "CNY"
        and usage["metadata"]["usd_per_cny"] == "0.15"
    )
    assert usage["metadata"]["original_cny"] == "0.0000045"
    assert requests[0]["input"] == ["我在学习智能体系统"]
    await save_memory(store, "我准备英语面试", 2)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(503))
    ) as http:
        worker = MemoryIndexWorker(
            store, configured(), EmbeddingClient(configured().embedding_config(), http)
        )
        assert await worker.work_once(111)
    assert (await store.one("SELECT state FROM kestri.usage WHERE state='unknown'"))[
        "state"
    ] == "unknown"
    assert (
        await store.one("SELECT status FROM kestri.memory_index_jobs WHERE status!='succeeded'")
    )["status"] == "retry_wait"


async def test_hybrid_paraphrase_model_selection_and_cache(vector_store: Any) -> None:
    store = vector_store
    relevant = await save_memory(store, "我正在准备软件工程求职作品集", 1)
    unrelated = await save_memory(store, "晚饭喜欢吃番茄炒蛋", 2)
    await semantic(store)
    await index_all(store, {relevant["content"]: VECTOR, unrelated["content"]: OTHER})
    run = await accept_run(store, "怎样展示 agent 开发能力找工作？", 3)
    requests = []
    model, ac, sc = offline_model(
        [model_tool_call("MemorySelection", {"ids": [str(relevant["id"])]}, "select")], requests
    )
    embeddings = []

    def respond(request: httpx.Request) -> httpx.Response:
        embeddings.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-v4",
                "data": [{"index": 0, "embedding": list(VECTOR)}],
                "usage": {"prompt_tokens": 15, "total_tokens": 15},
            },
        )

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            retriever = MemoryRetriever(
                store,
                Budget(configured(), RunControl(store, run["id"])),
                model,
                EmbeddingClient(configured().embedding_config(), http),
            )
            found = await retriever.retrieve(run, [HumanMessage(content=run["request"])])
            assert [r["id"] for r in found] == [relevant["id"]]
            assert await retriever.retrieve(run, []) == found
            assert len(requests) == len(embeddings) == 1
            assert requests[0]["max_tokens"] <= 512
            assert [t["function"]["name"] for t in requests[0]["tools"]] == ["MemorySelection"]
            assert (
                len(
                    await store.all(
                        "SELECT * FROM kestri.usage WHERE kind IN ('memory_query','memory_select')"
                    )
                )
                == 2
            )
    finally:
        await ac.aclose()
        sc.close()


async def test_invalid_selection_and_embedding_failure_fall_back_lexically(
    vector_store: Any,
) -> None:
    store = vector_store
    related = await save_memory(store, "我在学习智能体工程", 1)
    await save_memory(store, "晚饭喜欢吃番茄炒蛋", 2)
    await semantic(store)
    await index_all(store)
    run = await accept_run(store, "智能体工程", 3)
    model, ac, sc = offline_model(
        [model_tool_call("MemorySelection", {"ids": [str(uuid4())]}, "select")],
        [],
    )
    try:
        for status in (200, 503):

            def respond(request: httpx.Request, status: int = status) -> httpx.Response:
                return httpx.Response(
                    status,
                    json={
                        "model": "text-embedding-v4",
                        "data": [{"index": 0, "embedding": list(VECTOR)}],
                        "usage": {"prompt_tokens": 5, "total_tokens": 5},
                    },
                )

            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
                retriever = MemoryRetriever(
                    store,
                    Budget(configured(), RunControl(store, run["id"])),
                    model,
                    EmbeddingClient(configured().embedding_config(), http),
                )
                found = await retriever.retrieve(run, [])
                assert [r["id"] for r in found] == [related["id"]]
        assert (
            len(
                await store.all(
                    "SELECT * FROM kestri.events WHERE kind='memory_retrieval_fallback'"
                )
            )
            == 2
        )
    finally:
        await ac.aclose()
        sc.close()


async def test_use_off_cancels_index_and_stale_foreground(vector_store: Any) -> None:
    store = vector_store
    await save_memory(store, "我在学习智能体工程")
    await semantic(store)
    async with httpx.AsyncClient() as http:
        worker = MemoryIndexWorker(
            store, configured(), EmbeddingClient(configured().embedding_config(), http)
        )
        job = await worker.claim(111)
        run = await accept_run(store, "智能体工程", 2)
        await semantic(store, 51, mode="use", enabled=False)
        with pytest.raises(PolicyDenied):
            await worker.publish(job, VECTOR)
        with pytest.raises(PolicyDenied):
            await RunControl(store, run["id"]).ensure_active()
    assert not await MemoryService(store, configured()).retrieve(run)
    assert not await store.all("SELECT * FROM kestri.memory_embeddings")


async def test_index_budget_shared_monthly_cap(vector_store: Any) -> None:
    store = vector_store
    await save_memory(store, "我在学习智能体工程")
    await semantic(store)
    async with httpx.AsyncClient() as http:
        worker = MemoryIndexWorker(
            store, configured(), EmbeddingClient(configured().embedding_config(), http)
        )
        job = await worker.claim(111)
        budget = IndexBudget(
            configured(memory_maintenance_monthly_usd="0.001"), IndexControl(worker, job)
        )
        await budget.reserve("index", 1000)
        with pytest.raises(BudgetExceeded):
            await budget.reserve("index", 1)


async def test_backup_omits_vectors_restore_disables_all_memory_use(
    vector_store: Any, tmp_path: Path
) -> None:
    store = vector_store
    await store.bind_identity(123, 111)
    await save_memory(store, "我在学习智能体工程")
    await semantic(store)
    await index_all(store)
    service = DataService(store, Workspace(tmp_path / "source"), configured())
    path = await service.backup(tmp_path / "bundle.json")
    payload = read_private(path)
    assert payload["schema"] == 6 and "memory_embeddings" not in payload["tables"]
    assert payload["tables"]["memory_index_jobs"]
    await store.execute("TRUNCATE " + ",".join("kestri." + name for name in TABLES) + " CASCADE")
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        exists = await store.one("SELECT to_regclass(%s) AS name", ("public." + table,))
        if exists["name"]:
            await store.execute("DELETE FROM public." + table)
    await DataService(store, Workspace(tmp_path / "target"), configured()).restore(path, apply=True)
    state = await store.one("SELECT * FROM kestri.conversations")
    assert (
        not state["memory_use_enabled"]
        and not state["memory_semantic_enabled"]
        and not state["auto_memory_enabled"]
    )
    assert not await store.all("SELECT * FROM kestri.memory_embeddings")
    assert (await store.one("SELECT status FROM kestri.memory_index_jobs"))["status"] == "cancelled"


async def test_cleanup_invalidates_vector_of_auto_fact(vector_store: Any, tmp_path: Path) -> None:
    store = vector_store
    memory = await save_memory(store, "我在学习智能体工程")
    await semantic(store)
    await index_all(store)
    message = await store.one(
        "SELECT id,content FROM kestri.messages WHERE telegram_id=1 AND direction='in'"
    )
    await store.execute(
        "UPDATE kestri.memories SET origin='auto_direct' WHERE id=%s", (memory["id"],)
    )
    await store.execute(
        "INSERT INTO kestri.memory_sources(memory_id,message_id,quote,start_offset,end_offset) "
        "VALUES (%s,%s,%s,0,%s)",
        (memory["id"], message["id"], message["content"], len(message["content"])),
    )
    await store.execute("UPDATE kestri.outbox SET status='sent'")
    await store.execute(
        "UPDATE kestri.messages SET created_at=%s", (datetime.now(UTC) - timedelta(days=100),)
    )
    await DataService(store, Workspace(tmp_path), configured()).cleanup(apply=True)
    assert not await store.all("SELECT * FROM kestri.memory_embeddings")
    assert not await store.all("SELECT * FROM kestri.memory_sources")


async def test_disable_during_embedding_cannot_publish_or_inject(vector_store: Any) -> None:
    store = vector_store
    await save_memory(store, "我在学习智能体工程")
    await semantic(store)

    async def disabling(request: httpx.Request) -> httpx.Response:
        await semantic(store, 51, mode="use", enabled=False)
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-v4",
                "data": [{"index": 0, "embedding": list(VECTOR)}],
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(disabling)) as http:
        worker = MemoryIndexWorker(
            store, configured(), EmbeddingClient(configured().embedding_config(), http)
        )
        assert await worker.work_once(111)
    assert not await store.all("SELECT * FROM kestri.memory_embeddings")
    assert (await store.one("SELECT state FROM kestri.usage WHERE kind='memory_index'"))[
        "state"
    ] == "recorded"
    await semantic(store, 52, mode="use", enabled=True)
    await index_all(store)
    run = await accept_run(store, "智能体工程", 2)
    model, ac, sc = offline_model([], [])

    async def disabling_query(request: httpx.Request) -> httpx.Response:
        await semantic(store, 53, mode="use", enabled=False)
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-v4",
                "data": [{"index": 0, "embedding": list(VECTOR)}],
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            },
        )

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(disabling_query)) as http:
            retriever = MemoryRetriever(
                store,
                Budget(configured(), RunControl(store, run["id"])),
                model,
                EmbeddingClient(configured().embedding_config(), http),
            )
            with pytest.raises(PolicyDenied):
                await retriever.retrieve(run, [])
    finally:
        await ac.aclose()
        sc.close()


async def test_no_relevant_facts_returns_empty_without_recent_padding(vector_store: Any) -> None:
    store = vector_store
    await save_memory(store, "晚饭喜欢吃番茄炒蛋")
    await semantic(store)
    await index_all(store)
    run = await accept_run(store, "量子物理", 2)
    requests = []
    model, ac, sc = offline_model([], requests)

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-v4",
                "data": [{"index": 0, "embedding": list(OTHER)}],
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            },
        )

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            retriever = MemoryRetriever(
                store,
                Budget(configured(), RunControl(store, run["id"])),
                model,
                EmbeddingClient(configured().embedding_config(), http),
            )
            assert await retriever.retrieve(run, []) == []
            assert requests == []
    finally:
        await ac.aclose()
        sc.close()


async def test_legacy_schema5_restore_defaults_and_no_vector_replay(
    vector_store: Any, tmp_path: Path
) -> None:
    import hashlib

    from kestri.data import encoded, write_private

    store = vector_store
    await store.bind_identity(123, 111)
    await save_memory(store, "回答使用中文")
    source = DataService(store, Workspace(tmp_path / "source"), configured())
    bundle = read_private(await source.backup(tmp_path / "original.json"))
    bundle["schema"] = 5
    del bundle["tables"]["memory_index_jobs"]
    for row in bundle["tables"]["conversations"]:
        for field in (
            "memory_use_enabled",
            "memory_semantic_enabled",
            "memory_retrieval_generation",
            "memory_embedding_space",
        ):
            del row[field]
    path = tmp_path / "legacy.json"
    write_private(
        path, encoded({"payload": bundle, "sha256": hashlib.sha256(encoded(bundle)).hexdigest()})
    )
    await store.execute("TRUNCATE " + ",".join("kestri." + name for name in TABLES) + " CASCADE")
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        exists = await store.one("SELECT to_regclass(%s) AS name", ("public." + table,))
        if exists["name"]:
            await store.execute("DELETE FROM public." + table)
    await DataService(store, Workspace(tmp_path / "restored"), configured()).restore(
        path, apply=True
    )
    assert not (await store.one("SELECT memory_use_enabled FROM kestri.conversations"))[
        "memory_use_enabled"
    ]
    assert not await store.all("SELECT * FROM kestri.memory_index_jobs")
    assert not await store.all("SELECT * FROM kestri.memory_embeddings")


async def test_real_research_path_injects_ephemerally(vector_store: Any, tmp_path: Path) -> None:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from kestri.research import ResearchAgent

    store = vector_store
    memory = await save_memory(store, "我正在准备软件求职作品集")
    await semantic(store)
    await index_all(store)
    run = await accept_run(store, "怎么展示 agent 工程能力？", 2)
    requests = []
    model, ac, sc = offline_model(
        [
            model_tool_call("MemorySelection", {"ids": [str(memory["id"])]}, "select"),
            {"role": "assistant", "content": "建议展示工具调用与恢复流程。"},
        ],
        requests,
    )

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-v4",
                "data": [{"index": 0, "embedding": list(VECTOR)}],
                "usage": {"prompt_tokens": 10, "total_tokens": 10},
            },
        )

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            saver = AsyncPostgresSaver(store.pool)
            await saver.setup()
            agent = ResearchAgent(configured(), store, Workspace(tmp_path), saver, model, http)
            await agent.run(run, RunControl(store, run["id"]))
            assert (await store.one("SELECT status FROM kestri.runs WHERE id=%s", (run["id"],)))[
                "status"
            ] == "completed"
            assert len(requests) == 2
            system = next(m["content"] for m in requests[1]["messages"] if m["role"] == "system")
            assert memory["content"] in system and "Selected current owner memory" in system
            snapshot = await saver.aget_tuple({"configurable": {"thread_id": run["id"]}})
            assert snapshot is not None
            assert all(
                memory["content"] not in m.text
                for m in snapshot.checkpoint["channel_values"]["messages"]
            )
    finally:
        await ac.aclose()
        sc.close()
