from typing import Any

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from kestri.agent.budget import RunControl
from kestri.agent.research import ResearchAgent
from kestri.memory.diagnostics import explain
from kestri.memory.management import MemoryAction, MemoryManager, MemoryPlan
from kestri.storage.workspace import Workspace
from tests.helpers import (
    TEST_DSN,
    accept_memory_control_run,
    accept_run,
    model_tool_call,
    offline_model,
    research_settings,
    save_memory,
)
from tests.memory.helpers import apply_control

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="Set a dedicated KESTRI_TEST_DATABASE_URL")


async def test_real_framework_management_commits_then_survives_epoch_reset(
    store: Any, tmp_path: Any
) -> None:
    text = "帮我开启自动记忆。"
    row = await accept_memory_control_run(store, text, 1)
    plan = MemoryPlan(
        actions=[MemoryAction(action="set", setting="auto", enabled=True, evidence="开启自动记忆")]
    )
    requests = []
    model, client, sync = offline_model(
        [model_tool_call("MemoryPlan", plan.model_dump(), "plan")], requests
    )
    try:
        await MemoryManager(research_settings(), store, model).run(
            row, RunControl(store, row["id"])
        )
    finally:
        await client.aclose()
        sync.close()
    assert (await store.one("SELECT auto_memory_enabled FROM kestri.conversations"))[
        "auto_memory_enabled"
    ]
    assert (await store.one("SELECT status FROM kestri.runs"))["status"] == "completed"
    assert [t["function"]["name"] for t in requests[0]["tools"]] == ["MemoryPlan"]
    assert len(requests) == 1
    await store.recover()
    assert len(await store.all("SELECT * FROM kestri.memory_changes")) == 1
    receipt = await store.one(
        "SELECT * FROM kestri.outbox WHERE content LIKE %s", ("已开启自动记忆%",)
    )
    assert receipt["presentation"]["parse_mode"] == "HTML"
    assert await store.delivery_current(receipt)


async def test_numbered_choice_survives_store_restart_and_stale_revision_denied(store: Any) -> None:
    await save_memory(store, "Python 用于后端。", 1)
    await save_memory(store, "Python 用于数据分析。", 2)
    await apply_control(store, "忘记关于Python的记忆", 3)
    choice = (await store.one("SELECT memory_choice FROM kestri.conversations"))["memory_choice"]
    target = choice["targets"][1]["id"]
    await store.open()
    assert "已忘记" in await apply_control(store, "第二条", 4)
    assert (await store.one("SELECT status FROM kestri.memories WHERE id = %s", (target,)))[
        "status"
    ] == "forgotten"
    assert "失效" in await apply_control(store, "第二条", 5)
    await save_memory(store, "Python 还用于 CLI。", 6)
    await apply_control(store, "忘记关于Python的记忆", 7)
    choice = (await store.one("SELECT memory_choice FROM kestri.conversations"))["memory_choice"]
    await store.execute(
        "UPDATE kestri.memories SET revision = revision+1 WHERE id = %s",
        (choice["targets"][0]["id"],),
    )
    assert "已变更" in await apply_control(store, "第一条", 8)
    assert len(await store.all("SELECT * FROM kestri.memories WHERE status='active'")) == 2


async def test_diagnostic_actual_injection_then_forget_suppresses_content(
    store: Any, tmp_path: Any
) -> None:
    memory = await save_memory(store, "我点菜喜欢清淡不辣。", 1)
    row = await accept_run(store, "我点菜的偏好是什么？", 2)
    requests = []
    model, client, sync = offline_model(
        [{"role": "assistant", "content": "喜欢清淡不辣。"}], requests
    )
    settings = research_settings(evidence_dir=tmp_path)
    saver = AsyncPostgresSaver(store.pool)
    await saver.setup()
    try:
        agent = ResearchAgent(settings, store, Workspace(tmp_path), saver, model, client)
        await agent.run(row, RunControl(store, row["id"]))
    finally:
        await client.aclose()
        sync.close()
    event = await store.one("SELECT metadata FROM kestri.events WHERE kind='memory_injected'")
    assert event["metadata"]["memories"][0]["id"] == str(memory["id"])
    assert "content" not in str(event["metadata"])
    async with store.pool.connection() as conn:
        before = await explain(conn, 111)
    assert "清淡不辣" in before and str(memory["id"])[:8] in before
    await apply_control(store, f"/forget {memory['id']}", 3)
    async with store.pool.connection() as conn:
        after = await explain(conn, 111)
    assert "清淡不辣" not in after and "不再展示" in after


async def test_malformed_multi_command_and_stale_pending_view_do_not_apply(store: Any) -> None:
    await store.accept(1, 111, 1, "/memory auto on\n/memory semantic on", None, "memory", 8)
    state = await store.one(
        "SELECT auto_memory_enabled,memory_semantic_enabled FROM kestri.conversations"
    )
    assert state == {"auto_memory_enabled": False, "memory_semantic_enabled": False}
    memory = await save_memory(store, "私人测试事实", 2)
    await store.accept(3, 111, 3, "/memory", None, "memory", 8)
    view = await store.one("SELECT * FROM kestri.outbox WHERE reply_to=3")
    await apply_control(store, f"/forget {memory['id']}", 4)
    assert not await store.delivery_current(view)
    assert (await store.one("SELECT content FROM kestri.outbox WHERE id = %s", (view["id"],)))[
        "content"
    ] == ""


async def test_batch_settings_reports_unavailable_semantic_without_claiming_success(
    store: Any,
) -> None:
    text = "开启自动记忆和语义检索"
    row = await accept_memory_control_run(store, text, 1)
    plan = MemoryPlan(
        actions=[
            MemoryAction(action="set", setting="auto", enabled=True, evidence=text),
            MemoryAction(action="set", setting="semantic", enabled=True, evidence=text),
        ]
    )
    model, client, sync = offline_model([], [])
    try:
        reply = await MemoryManager(research_settings(), store, model).apply(row, plan)
    finally:
        await client.aclose()
        sync.close()
    assert "已开启自动记忆" in reply and "未开启" in reply
    state = await store.one(
        "SELECT auto_memory_enabled,memory_semantic_enabled FROM kestri.conversations"
    )
    assert state == {"auto_memory_enabled": True, "memory_semantic_enabled": False}
    await store.finish(row["id"], "completed", reply)
    assert (await store.one("SELECT status FROM kestri.runs"))["status"] == "completed"


async def test_restore_drops_choice_and_actual_diagnostics(store: Any, tmp_path: Any) -> None:
    from kestri.storage.lifecycle import DataService

    await store.bind_identity(123, 111)
    await save_memory(store, "Python 后端", 1)
    await save_memory(store, "Python 分析", 2)
    await apply_control(store, "忘记关于Python的记忆", 3)
    run = await accept_run(store, "测试诊断", 4)
    await store.event(run["id"], "memory_injected", {"method": "lexical", "memories": []})
    await store.finish(run["id"], "completed", "测试回答")
    source = DataService(store, Workspace(tmp_path / "source"), research_settings())
    path = await source.backup(tmp_path / "backup.json")
    await store.execute("DROP SCHEMA kestri CASCADE")
    await store.open()
    for name in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        exists = await store.one("SELECT to_regclass(%s) AS name", (f"public.{name}",))
        if exists["name"]:
            await store.execute(f"DELETE FROM public.{name}")
    target = DataService(store, Workspace(tmp_path / "target"), research_settings())
    await target.restore(path, apply=True)
    assert (await store.one("SELECT memory_choice FROM kestri.conversations"))[
        "memory_choice"
    ] is None
    assert not await store.all("SELECT * FROM kestri.events WHERE kind='memory_injected'")
    assert all(
        r["presentation"] is None for r in await store.all("SELECT presentation FROM kestri.outbox")
    )
