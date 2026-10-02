import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from kestri.agent.budget import Budget, RunControl
from kestri.agent.research import ResearchAgent
from kestri.errors import PolicyDenied, ProviderFailure
from kestri.history.retriever import (
    HistoryReadInput,
    HistoryRetriever,
    HistorySearchInput,
    instant,
    segment,
)
from kestri.storage.workspace import Workspace
from tests.helpers import (
    accept_run,
    create_task,
    model_tool_call,
    offline_model,
    research_settings,
)


async def enabled(store: Any) -> None:
    await store.accept(100, 111, 100, "/memory auto on", None, "memory", 8)


async def old_turn(store: Any, text: str, identity: int = 1) -> dict:
    row = await accept_run(store, text, identity)
    await store.finish(row["id"], "completed", "助手建议，非主人决定")
    return row


def retriever(store: Any, row: dict, **settings: Any) -> HistoryRetriever:
    return HistoryRetriever(
        store, Budget(research_settings(**settings), RunControl(store, row["id"])), row
    )


def test_history_schemas_times_and_complete_turn_limits() -> None:
    for args in ({"query": " "}, {"query": "a", "limit": 6}, {"query": "a", "chat_id": 111}):
        with pytest.raises(ValidationError):
            HistorySearchInput(**args)
    with pytest.raises(ValidationError):
        HistoryReadInput(segment_id="1")
    with pytest.raises(ValueError):
        instant("2026-10-02")
    now = datetime.now(UTC)
    base = {"id": 1, "direction": "in", "content": "历史", "telegram_id": 1, "created_at": now}
    assert segment([base])["messages"][0]["role"] == "owner"
    assert segment([{**base, "content": "字" * 8001}]) is None
    assert segment([base] * 13) is None
    assert segment([{**base, "direction": "out"}]) is None


async def test_history_default_denial_then_lexical_handles_and_dates(store: Any) -> None:
    await old_turn(store, "旧历史智能体", 1)
    await enabled(store)
    turn = await old_turn(store, "我决定周末学习智能体", 2)
    await store.execute(
        "INSERT INTO kestri.messages(chat_id,telegram_id,direction,content,run_id,provenance) "
        "VALUES (111,200,'out','助手建议学习英语',%s,'context')",
        (turn["id"],),
    )
    row = await accept_run(store, "以前决定学习什么？", 3)
    history = retriever(store, row)
    result = json.loads(await history.search("学习智能体"))
    assert len(result["results"]) == 1
    handle = result["results"][0]["segment_id"]
    read = json.loads(await history.read(handle))
    assert read["messages"][0]["content"] == turn["request"]
    assert read["messages"][0]["role"] == "owner"
    assert read["messages"][1]["role"] == "assistant"
    assert not read["truncated"]
    assert json.loads(await history.search("毫不相关的橘子"))["results"] == []
    assert json.loads(await history.search("学习", before="2000-01-01T00:00:00Z"))["results"] == []
    with pytest.raises(ValueError):
        await history.search("学习", after="2030-01-01T00:00:00Z", before="2000-01-01T00:00:00Z")
    with pytest.raises(PolicyDenied):
        await retriever(store, row).read(handle)
    await store.accept(101, 111, 101, "/memory auto off", None, "memory", 8)
    with pytest.raises(PolicyDenied):
        await history.read(handle)
    assert (await store.one("SELECT thread_id FROM kestri.conversations"))["thread_id"] is None


async def test_history_source_hash_purge_floor_use_and_owner_scope(store: Any) -> None:
    await enabled(store)
    await old_turn(store, "周末学习智能体", 1)
    # Foreign owner and forwarded source must not leak.
    await store.accept(10, 222, 10, "学习外国私人秘密", None, None, 8)
    await store.execute("UPDATE kestri.runs SET status='completed' WHERE chat_id=222")
    await store.accept(11, 111, 11, "学习转发秘密", None, None, 8, provenance="forwarded")
    await store.execute("UPDATE kestri.runs SET status='completed' WHERE request='学习转发秘密'")
    row = await accept_run(store, "查找学习", 2)
    history = retriever(store, row)
    result = json.loads(await history.search("学习"))["results"]
    assert len(result) == 1
    handle = result[0]["segment_id"]
    await store.execute(
        "UPDATE kestri.messages SET content='新内容' WHERE direction='in' AND telegram_id=1"
    )
    with pytest.raises(PolicyDenied):
        await history.read(handle)
    await store.execute("DELETE FROM kestri.messages WHERE telegram_id=1 AND direction='in'")
    assert json.loads(await history.search("学习"))["results"] == []
    await store.execute(
        "UPDATE kestri.conversations SET automatic_history_floor=999 WHERE chat_id=111"
    )
    assert json.loads(await history.search("新内容"))["results"] == []
    await store.execute(
        "UPDATE kestri.conversations SET memory_use_enabled=false WHERE chat_id=111"
    )
    with pytest.raises(PolicyDenied):
        await history.search("学习")


async def test_history_skips_oversize_secrets_and_rejects_overflow(store: Any) -> None:
    await enabled(store)
    await old_turn(store, "学习" * 5000, 1)
    await old_turn(store, "学习 password=super-secret-test", 2)
    await old_turn(store, "学习" * 1500, 3)
    row = await accept_run(store, "查历史", 4)
    history = retriever(store, row, tool_output_chars=2000)
    result = json.loads(await history.search("学习"))["results"]
    assert len(result) == 1
    with pytest.raises(ProviderFailure):
        await history.read(result[0]["segment_id"])


async def test_history_search_limit_and_time_window(store: Any) -> None:
    await enabled(store)
    for i in range(1, 8):
        await old_turn(store, f"学习项目 {i}", i)
    row = await accept_run(store, "回忆", 8)
    history = retriever(store, row)
    assert len(json.loads(await history.search("学习"))["results"]) == 5
    assert len(json.loads(await history.search("学习", limit=2))["results"]) == 2
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert json.loads(await history.search("学习", after=future))["results"] == []


async def test_history_real_graph_tools_are_available_only_when_enabled(
    store: Any, tmp_path: Any
) -> None:
    await enabled(store)
    await old_turn(store, "周末学习智能体", 1)
    row = await accept_run(store, "我以前决定做什么？", 2)
    handle = json.loads(await retriever(store, row).search("学习智能体"))["results"][0][
        "segment_id"
    ]
    requests: list[dict] = []
    model, async_client, sync_client = offline_model(
        [
            model_tool_call("search_history", {"query": "学习智能体"}, "history-call"),
            model_tool_call("read_history_segment", {"segment_id": handle}, "history-read"),
            {"role": "assistant", "content": "你说过周末学习智能体。"},
        ],
        requests,
    )
    try:
        agent = ResearchAgent(
            research_settings(), store, Workspace(tmp_path), InMemorySaver(), model, async_client
        )
        await agent.run(row, RunControl(store, row["id"]))
        assert (await store.one("SELECT status FROM kestri.runs WHERE id=%s", (row["id"],)))[
            "status"
        ] == "completed"
        names = {item["function"]["name"] for item in requests[0]["tools"]}
        assert {"search_history", "read_history_segment"} <= names
        returned = [m for m in requests[1]["messages"] if m["role"] == "tool"]
        assert "周末学习智能体" in returned[0]["content"]
        read_returned = [m for m in requests[2]["messages"] if m["role"] == "tool"]
        assert json.loads(read_returned[-1]["content"])["messages"][0]["role"] == "owner"
        await store.accept(101, 111, 101, "/memory auto off", None, "memory", 8)
        row = await accept_run(store, "你好", 3)
        model2, client2, sync2 = offline_model([{"role": "assistant", "content": "你好"}], requests)
        try:
            await ResearchAgent(
                research_settings(), store, Workspace(tmp_path), InMemorySaver(), model2, client2
            ).run(row, RunControl(store, row["id"]))
            assert "search_history" not in {t["function"]["name"] for t in requests[-1]["tools"]}
        finally:
            await client2.aclose()
            sync2.close()
    finally:
        await async_client.aclose()
        sync_client.close()


async def test_history_default_off_and_expired_runs_task_scope(store: Any) -> None:
    row = await accept_run(store, "查历史", 1)
    with pytest.raises(PolicyDenied):
        await retriever(store, row).search("学习")
    await store.finish(row["id"], "completed", "done")
    await enabled(store)
    old = await old_turn(store, "学习过期内容", 2)
    await store.execute("UPDATE kestri.runs SET history_expired=true WHERE id=%s", (old["id"],))
    row = await accept_run(store, "查历史", 3)
    assert json.loads(await retriever(store, row).search("学习"))["results"] == []
    row["kind"] = "background"
    with pytest.raises(PolicyDenied):
        await retriever(store, row).search("学习")


async def test_history_disable_during_lookup_denies_output(store: Any, monkeypatch: Any) -> None:
    await enabled(store)
    await old_turn(store, "学习智能体", 1)
    row = await accept_run(store, "查历史", 2)
    history = retriever(store, row)
    original = history.turns

    async def disable(*args: Any, **kwargs: Any) -> Any:
        result = await original(*args, **kwargs)
        await store.execute("UPDATE kestri.conversations SET memory_use_enabled=false")
        return result

    monkeypatch.setattr(history, "turns", disable)
    with pytest.raises(PolicyDenied):
        await history.search("学习")


async def test_history_current_task_scope_and_newest_200_window(store: Any) -> None:
    await enabled(store)
    task = await create_task(store, 2000)
    private = await old_turn(store, "学习任务私有内容", 1)
    await store.execute(
        "UPDATE kestri.messages SET task_id=%s WHERE run_id=%s", (task["id"], private["id"])
    )
    row = await accept_run(store, "查询", 2)
    assert json.loads(await retriever(store, row).search("学习任务"))["results"] == []
    row["task_id"] = task["id"]
    assert len(json.loads(await retriever(store, row).search("学习任务"))["results"]) == 1
    await store.finish(row["id"], "completed", "done")
    for i in range(3, 203):
        await old_turn(store, "没有匹配主题", i + 300)
    row = await accept_run(store, "查询", 204)
    row["task_id"] = task["id"]
    result = json.loads(await retriever(store, row).search("学习任务"))
    assert result["results"] == []
    assert "200" in result["coverage"]
