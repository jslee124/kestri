import json
from typing import Any

import httpx
import pytest

from kestri.agent.budget import Budget, RunControl
from kestri.history.retriever import HistoryRetriever
from kestri.integrations.embedding import EmbeddingClient
from kestri.memory.embedding import embedding_space
from tests.helpers import accept_run, research_settings
from tests.history.test_history_integration import enabled, old_turn

V = [1.0] + [0.0] * 1023


def settings() -> Any:
    return research_settings(
        DASHSCOPE_API_KEY="history-embedding-test",
        embedding_base_url="https://test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    )


@pytest.fixture
async def ready(store: Any) -> Any:
    row = await store.one("SELECT to_regclass('kestri.history_embeddings') AS name")
    if not row["name"]:
        pytest.skip("pgvector matrix leg required for semantic history")
    await enabled(store)
    store.embedding_space = embedding_space(settings().embedding_config())
    await store.accept(101, 111, 101, "/memory semantic on", None, "memory", 8)
    return store


def response(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "model": body["model"],
            "data": [{"index": i, "embedding": V} for i in range(len(body["input"]))],
            "usage": {"prompt_tokens": 10, "total_tokens": 10},
        },
    )


def history(store: Any, run: Any, http: httpx.AsyncClient) -> HistoryRetriever:
    return HistoryRetriever(
        store,
        Budget(settings(), RunControl(store, run["id"])),
        run,
        EmbeddingClient(settings().embedding_config(), http),
    )


async def test_dense_only_history_recall_cache_and_audited_batch(ready: Any) -> None:
    store = ready
    await old_turn(store, "我不吃肉", 1)
    run = await accept_run(store, "回忆饮食", 2)
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        retriever = history(store, run, http)
        first = json.loads(await retriever.search("vegetarian"))
        assert first["method"] == "bounded_hybrid"
        assert first["indexed_turns"] == 1 and len(first["results"]) == 1
        assert len(requests[0]["input"]) == 2
        assert "owner" in requests[0]["input"][1]
        await retriever.read(first["results"][0]["segment_id"])
        assert len(json.loads(await retriever.search("vegetarian"))["results"]) == 1
        assert len(requests) == 1
    usage = await store.one("SELECT * FROM kestri.usage WHERE kind='history_retrieval'")
    assert usage["state"] == "recorded" and usage["metadata"]["original_currency"] == "CNY"
    assert "我不吃肉" not in json.dumps(usage["metadata"], ensure_ascii=False)
    assert (await store.one("SELECT count(*) AS n FROM kestri.history_embeddings"))["n"] == 1


async def test_semantic_failure_has_lexical_fallback_and_unknown_cost(ready: Any) -> None:
    store = ready
    await old_turn(store, "学习智能体", 1)
    run = await accept_run(store, "回忆", 2)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(503))
    ) as http:
        result = json.loads(await history(store, run, http).search("学习"))
        assert result["method"] == "bounded_lexical" and result["fallback"] == "SemanticUnavailable"
        assert len(result["results"]) == 1
    assert (await store.one("SELECT state FROM kestri.usage WHERE kind='history_retrieval'"))[
        "state"
    ] == "unknown"
    assert not await store.all("SELECT * FROM kestri.history_embeddings")


async def test_cache_source_append_edit_expiry_and_setting_purge(ready: Any) -> None:
    store = ready
    old = await old_turn(store, "学习智能体", 1)
    run = await accept_run(store, "回忆", 2)
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        await history(store, run, http).search("学习")
        assert len(await store.all("SELECT * FROM kestri.history_embeddings")) == 1
        await store.execute(
            "INSERT INTO kestri.messages(chat_id,direction,content,run_id,provenance) "
            "VALUES (111,'out','助手提案',%s,'context')",
            (old["id"],),
        )
        assert not await store.all("SELECT * FROM kestri.history_embeddings")
        await history(store, run, http).search("学习")
        assert len(await store.all("SELECT * FROM kestri.history_embeddings")) == 1
        await store.execute("UPDATE kestri.messages SET content='改为学英语' WHERE telegram_id=1")
        assert not await store.all("SELECT * FROM kestri.history_embeddings")
        await history(store, run, http).search("学英语")
        assert len(await store.all("SELECT * FROM kestri.history_embeddings")) == 1
        await store.execute("UPDATE kestri.runs SET history_expired=true WHERE id=%s", (old["id"],))
        assert not await store.all("SELECT * FROM kestri.history_embeddings")
        await store.execute(
            "UPDATE kestri.runs SET history_expired=false WHERE id=%s", (old["id"],)
        )
        await history(store, run, http).search("学英语")
        await store.accept(102, 111, 102, "/memory semantic off", None, "memory", 8)
        assert not await store.all("SELECT * FROM kestri.history_embeddings")


async def test_disable_during_provider_response_blocks_cache_and_output(ready: Any) -> None:
    store = ready
    await old_turn(store, "学习智能体", 1)
    run = await accept_run(store, "回忆", 2)

    async def respond(request: httpx.Request) -> httpx.Response:
        await store.accept(102, 111, 102, "/memory use off", None, "memory", 8)
        return response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        from kestri.errors import PolicyDenied

        with pytest.raises(PolicyDenied):
            await history(store, run, http).search("学习")
    assert not await store.all("SELECT * FROM kestri.history_embeddings")
    assert (await store.one("SELECT state FROM kestri.usage WHERE kind='history_retrieval'"))[
        "state"
    ] == "recorded"


async def test_progressive_coverage_query_limits_and_cascade(ready: Any) -> None:
    store = ready
    for i in range(1, 12):
        await old_turn(store, f"学习项目 {i}", i)
    run = await accept_run(store, "回忆", 12)
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        retriever = history(store, run, http)
        result = json.loads(await retriever.search("学习"))
        assert result["indexed_turns"] == 9 and result["eligible_turns"] == 11
        assert len(calls[0]["input"]) == 10
        for query in ("项目", "课程"):
            await retriever.search(query)
        fallback = json.loads(await retriever.search("计划"))
        assert fallback["fallback"] == "SemanticUnavailable"
        assert len(calls) == 3
        await store.execute("DELETE FROM kestri.messages WHERE direction='in' AND telegram_id=11")
        assert (await store.one("SELECT count(*) AS n FROM kestri.history_embeddings"))["n"] == 8


async def test_actual_graph_semantic_history_search_read_and_backup(
    ready: Any, tmp_path: Any
) -> None:
    from langgraph.checkpoint.memory import InMemorySaver

    from kestri.agent.research import ResearchAgent
    from kestri.storage.lifecycle import TABLES, DataService, read_private
    from kestri.storage.workspace import Workspace
    from tests.helpers import model_tool_call, offline_model

    store = ready
    await store.bind_identity(123, 111)
    await old_turn(store, "我不吃肉", 1)
    run = await accept_run(store, "以前的饮食习惯", 2)
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        lookup = history(store, run, http)
        handle = (await lookup.turns(await lookup.state(), None, None))[0]["id"]
        requests: list[dict] = []
        model, model_http, sync = offline_model(
            [
                model_tool_call("search_history", {"query": "vegetarian"}, "hs"),
                model_tool_call("read_history_segment", {"segment_id": handle}, "hr"),
                {"role": "assistant", "content": "你曾说过不吃肉。"},
            ],
            requests,
        )
        try:
            await ResearchAgent(
                settings(), store, Workspace(tmp_path), InMemorySaver(), model, http
            ).run(run, RunControl(store, run["id"]))
            final = await store.one("SELECT status FROM kestri.runs WHERE id=%s", (run["id"],))
            assert final["status"] == "completed"
            tools = [m for m in requests[2]["messages"] if m["role"] == "tool"]
            assert json.loads(tools[0]["content"])["method"] == "bounded_hybrid"
            assert "我不吃肉" in tools[1]["content"]
        finally:
            await model_http.aclose()
            sync.close()
    assert await store.all("SELECT * FROM kestri.history_embeddings")
    backup = await DataService(store, Workspace(tmp_path), settings()).backup(
        tmp_path / "backup.json"
    )
    assert "history_embeddings" not in read_private(backup)["tables"]
    await store.execute("TRUNCATE " + ",".join("kestri." + name for name in TABLES) + " CASCADE")
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        exists = await store.one("SELECT to_regclass(%s) AS name", ("public." + table,))
        if exists["name"]:
            await store.execute("DELETE FROM public." + table)
    await DataService(store, Workspace(tmp_path / "restored"), settings()).restore(
        backup, apply=True
    )
    assert not await store.all("SELECT * FROM kestri.history_embeddings")
    state = await store.one("SELECT * FROM kestri.conversations")
    assert not state["auto_memory_enabled"] and not state["memory_use_enabled"]
