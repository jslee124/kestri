"""Actual durable task authority, continuations and command/application behavior."""

from typing import Any

import httpx
import pytest

from kestri.agent.budget import RunControl
from kestri.errors import PolicyDenied
from kestri.tasks.agent import TaskAgent
from kestri.tasks.dialogue import prepare
from kestri.tasks.service import TaskPlan, TaskService
from tests.helpers import (
    TEST_DSN,
    accept_task_control_run,
    create_task,
    make_application,
    model_tool_call,
    offline_model,
    research_settings,
    telegram_update,
)

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="Set dedicated test database")


async def run_agent(store: Any, row: dict, responses: list[dict]) -> int:
    requests: list[dict] = []
    model, async_client, sync_client = offline_model(responses, requests)
    try:
        await TaskAgent(research_settings(), store, model).run(row, RunControl(store, row["id"]))
    finally:
        await async_client.aclose()
        sync_client.close()
    return len(requests)


async def test_choice_restart_consumes_only_selected_revision(store: Any) -> None:
    first = await create_task(store, 1)
    second = await create_task(store, 2)
    row = await accept_task_control_run(store, "暂停简报", 3)
    answer = await TaskService(store, research_settings()).apply(
        row, TaskPlan(action="pause"), "pause"
    )
    await store.finish(row["id"], "completed", answer)
    assert all(task["status"] == "active" for task in await store.all("SELECT * FROM kestri.tasks"))
    state = await store.one("SELECT memory_choice FROM kestri.conversations WHERE chat_id = 111")
    token = state["memory_choice"]["token"]
    await store.recover()
    row = await accept_task_control_run(store, f"选择任务 {token} 2", 4)
    assert await run_agent(store, row, []) == 0
    states = {
        str(task["id"]): task["status"] for task in await store.all("SELECT * FROM kestri.tasks")
    }
    assert states[str(first["id"])] == "active" and states[str(second["id"])] == "paused"
    row = await accept_task_control_run(store, f"选择任务 {token} 2", 5)
    assert await run_agent(store, row, []) == 0
    assert (await store.one("SELECT result FROM kestri.runs WHERE id = %s", (row["id"],)))[
        "result"
    ].startswith("这个任务选择")
    assert not await store.all("SELECT * FROM kestri.usage WHERE run_id = %s", (row["id"],))


async def test_supplement_and_reference_timing_use_real_structured_pipeline(store: Any) -> None:
    await create_task(store)
    row = await accept_task_control_run(store, "修改简报时间", 2)
    service = TaskService(store, research_settings())
    answer = await service.apply(row, TaskPlan(action="clarify"), "update")
    await store.finish(row["id"], "completed", answer)
    for identity, text, clock in [(3, "晚上八点", "20:00"), (4, "改到晚上九点", "21:00")]:
        row = await accept_task_control_run(store, text, identity)
        responses = [
            model_tool_call("TaskPlan", {"action": "update", "local_time": clock}, str(identity))
        ]
        expected_calls = 1 if identity == 3 else 0
        assert await run_agent(store, row, responses) == expected_calls
        assert (await store.one("SELECT local_time FROM kestri.tasks"))["local_time"] == clock
        assert (await store.one("SELECT status FROM kestri.runs WHERE id = %s", (row["id"],)))[
            "status"
        ] == "completed"


async def test_stale_target_and_source_cannot_commit(store: Any) -> None:
    await create_task(store, 1)
    await create_task(store, 2)
    row = await accept_task_control_run(store, "暂停简报", 3)
    service = TaskService(store, research_settings())
    answer = await service.apply(row, TaskPlan(action="pause"), "pause")
    await store.finish(row["id"], "completed", answer)
    row = await accept_task_control_run(store, "第二个", 4)
    async with store.pool.connection() as conn:
        context = await prepare(conn, row)
    assert context
    await store.execute("UPDATE kestri.tasks SET revision = revision + 1")
    with pytest.raises(PolicyDenied, match="TaskChoiceTargetChanged"):
        await service.apply(row, TaskPlan(action="pause"), "pause", continuation=context)
    await store.execute(
        "UPDATE kestri.runs SET history_expired = true WHERE id = %s", (context.sources[0],)
    )
    async with store.pool.connection() as conn:
        with pytest.raises(PolicyDenied, match="SourceUnavailable"):
            await prepare(conn, row)
    assert all(task["status"] == "active" for task in await store.all("SELECT * FROM kestri.tasks"))


async def test_runtime_fast_views_and_new_topic_clear_reference(store: Any) -> None:
    await create_task(store)
    async with httpx.AsyncClient() as client:
        app = make_application(store, client)
        for identity, text in [(2, "我有哪些任务？"), (3, "现在在做什么？"), (4, "开始新话题")]:
            assert await app.accept_update(
                telegram_update(update_id=identity, message_id=identity, text=text)
            )
    assert len(await store.all("SELECT * FROM kestri.runs")) == 1
    assert not (
        await store.one("SELECT memory_choice FROM kestri.conversations WHERE chat_id = 111")
    )["memory_choice"]
    output = await store.all("SELECT content, presentation FROM kestri.outbox ORDER BY sequence")
    assert any("你的持续任务" in item["content"] for item in output)
    assert any("当前没有进行中" in item["content"] for item in output)
    assert all(
        item["presentation"]["parse_mode"] == "HTML" for item in output if item["presentation"]
    )


async def test_partial_creation_accepts_time_but_not_unrelated_chat(store: Any) -> None:
    row = await accept_task_control_run(store, "每天 UTC 给我合成天气简报", 1)
    answer = await TaskService(store, research_settings()).apply(
        row, TaskPlan(action="clarify"), "create"
    )
    await store.finish(row["id"], "completed", answer)
    async with httpx.AsyncClient() as client:
        app = make_application(store, client)
        assert await app.accept_update(
            telegram_update(text="今天天气不错", update_id=2, message_id=2)
        )
    unrelated = await store.claim_run()
    assert unrelated["kind"] == "foreground"
    await store.finish(unrelated["id"], "completed", "普通聊天")
    row = await accept_task_control_run(store, "早上八点", 3)
    response = model_tool_call(
        "TaskPlan",
        {
            "action": "create",
            "instructions": "合成天气简报",
            "local_time": "08:00",
            "weekdays": list(range(7)),
            "timezone": "UTC",
        },
        "create-after-supplement",
    )
    assert await run_agent(store, row, [response]) == 1
    tasks = await store.all("SELECT * FROM kestri.tasks")
    assert len(tasks) == 1 and tasks[0]["local_time"] == "08:00"


async def test_expired_choices_and_new_topic_cannot_mutate(store: Any) -> None:
    await create_task(store, 1)
    await create_task(store, 2)
    row = await accept_task_control_run(store, "暂停简报", 3)
    answer = await TaskService(store, research_settings()).apply(
        row, TaskPlan(action="pause"), "pause"
    )
    await store.finish(row["id"], "completed", answer)
    await store.execute("""
        UPDATE kestri.conversations
        SET memory_choice = jsonb_set(memory_choice, '{expires}', '"2000-01-01T00:00:00+00:00"')
    """)
    row = await accept_task_control_run(store, "第二个", 4)
    assert await run_agent(store, row, []) == 0
    assert all(task["status"] == "active" for task in await store.all("SELECT * FROM kestri.tasks"))
    await store.accept(5, 111, 5, "开始新话题", None, "new", 8)
    assert not (
        await store.one("SELECT memory_choice FROM kestri.conversations WHERE chat_id = 111")
    )["memory_choice"]


async def test_natural_stop_cancels_current_run_and_mixed_controls_do_not_write(store: Any) -> None:
    await create_task(store)
    async with httpx.AsyncClient() as client:
        app = make_application(store, client)
        assert await app.accept_update(
            telegram_update(text="查询公开新闻", update_id=2, message_id=2)
        )
        active = await store.claim_run()
        assert await app.accept_update(
            telegram_update(
                text="帮我停止当前执行",
                update_id=3,
                message_id=3,
            )
        )
        assert await store.cancelled(active["id"])
        await store.finish(active["id"], "cancelled", "停止")
        before = await store.one("SELECT revision, status FROM kestri.tasks")
        for identity, text in [
            (4, "不要暂停新闻简报"),
            (5, "暂停简报并删除任务"),
            (6, "暂停新闻简报并开启自动记忆"),
        ]:
            assert await app.accept_update(
                telegram_update(
                    text=text,
                    update_id=identity,
                    message_id=identity,
                )
            )
        assert await store.one("SELECT revision, status FROM kestri.tasks") == before
        assert not (
            await store.one(
                "SELECT auto_memory_enabled FROM kestri.conversations WHERE chat_id = 111"
            )
        )["auto_memory_enabled"]


async def test_ambiguous_clarify_proposal_can_complete_selected_action(store: Any) -> None:
    await create_task(store, 1)
    second = await create_task(store, 2)
    row = await accept_task_control_run(store, "暂停简报", 3)
    answer = await TaskService(store, research_settings()).apply(
        row, TaskPlan(action="clarify", clarification="请选择目标任务"), "pause"
    )
    await store.finish(row["id"], "completed", answer)
    row = await accept_task_control_run(store, "第二个", 4)
    response = model_tool_call("TaskPlan", {"action": "pause"}, "selected-pause")
    assert await run_agent(store, row, [response]) == 1
    changed = await store.one("SELECT status FROM kestri.tasks WHERE id = %s", (second["id"],))
    assert changed["status"] == "paused"
    assert (await store.one("SELECT count(*) AS n FROM kestri.tasks WHERE status = 'active'"))[
        "n"
    ] == 1
