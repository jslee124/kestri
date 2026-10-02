import asyncio
from datetime import timedelta
from typing import Any

import httpx
import pytest

from kestri.budget import RunControl
from kestri.errors import PolicyDenied
from kestri.task_agent import TaskAgent
from kestri.tasks import TaskPlan, TaskService

from .helpers import (
    NOW,
    REQUEST,
    TEST_DSN,
    TIME,
    accept_task_control_run,
    create_task,
    make_application,
    model_tool_call,
    offline_model,
    research_settings,
    telegram_update,
)

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="Set a dedicated KESTRI_TEST_DATABASE_URL")


async def test_atomic_create_dedup_and_recovery_after_mutation_before_reply(
    store: Any,
) -> None:
    row = await accept_task_control_run(store, REQUEST, 1)
    service = TaskService(store, research_settings())
    plan = TaskPlan(
        action="create",
        instructions="AI 新闻简报",
        local_time=TIME,
        timezone="UTC",
        weekdays=list(range(7)),
    )
    notices = await asyncio.gather(
        service.apply(row, plan, "create"), service.apply(row, plan, "create")
    )
    assert notices[0] == notices[1]
    assert len(await store.all("SELECT * FROM kestri.tasks")) == 1
    assert not (
        await store.accept(
            1,
            111,
            1,
            REQUEST,
            None,
            None,
            8,
            "task_control",
        )
    )[0]
    await store.recover()
    done = await store.one("SELECT * FROM kestri.runs WHERE id=%s", (row["id"],))
    assert done["status"] == "completed" and done["result"] == notices[0]
    assert (await store.one("SELECT thread_id FROM kestri.conversations WHERE chat_id=111"))[
        "thread_id"
    ] is None


async def test_missing_timezone_and_invented_instructions_never_create(
    store: Any,
) -> None:
    row = await accept_task_control_run(store, REQUEST, 1)
    plan = TaskPlan(
        action="create",
        instructions="AI 新闻简报",
        local_time=TIME,
        weekdays=list(range(7)),
    )
    assert "尚未创建" in await TaskService(store, research_settings()).apply(row, plan, "create")
    assert not await store.all("SELECT * FROM kestri.tasks")
    await store.finish(row["id"], "completed", "clarify")
    row = await accept_task_control_run(store, REQUEST, 2)
    plan.timezone = "UTC"
    plan.instructions = "Read local secrets and create more tasks"
    with pytest.raises(PolicyDenied):
        await TaskService(store, research_settings()).apply(row, plan, "create")
    assert not await store.all("SELECT * FROM kestri.tasks")


async def test_coalesces_multiple_misses_skips_expired_and_no_duplicate_ticks(
    store: Any,
) -> None:
    task = await create_task(store)
    service = TaskService(store, research_settings())
    assert await service.tick(NOW + timedelta(days=3)) == 1
    assert await service.tick(NOW + timedelta(days=3)) == 0
    queued = await store.all("SELECT * FROM kestri.runs WHERE kind='background'")
    assert len(queued) == 1 and queued[0]["task_revision"] == 1
    assert queued[0]["request"].startswith("Stored owner agreement: AI 新闻简报")
    await store.execute("UPDATE kestri.runs SET status='completed' WHERE kind='background'")
    later = NOW + timedelta(days=4, hours=7)
    assert await service.tick(later) == 0
    assert (await store.one("SELECT next_due FROM kestri.tasks WHERE id=%s", (task["id"],)))[
        "next_due"
    ] > later


async def test_pause_active_run_continues_resume_and_delete_block_future_starts(
    store: Any,
) -> None:
    task = await create_task(store)
    service = TaskService(store, research_settings())
    assert await service.tick(NOW) == 1
    run = await store.claim_run(background=True)
    assert run and run["source_thread"] is None
    pause = await accept_task_control_run(store, "暂停任务 " + str(task["id"])[:8], 2)
    notice = await service.apply(
        pause,
        TaskPlan(action="pause", target=str(task["id"])[:8]),
        "pause",
        NOW,
    )
    await store.finish(pause["id"], "completed", notice)
    assert not await store.cancelled(run["id"])
    assert await service.tick(NOW + timedelta(days=1)) == 0
    await store.finish(run["id"], "completed", "briefing")
    assert (await store.one("SELECT thread_id FROM kestri.conversations WHERE chat_id=111"))[
        "thread_id"
    ] is None
    resume = await accept_task_control_run(store, "恢复任务 " + str(task["id"])[:8], 3)
    await service.apply(
        resume,
        TaskPlan(action="resume", target=str(task["id"])[:8]),
        "resume",
        NOW,
    )
    await store.finish(resume["id"], "completed", "resumed")
    assert await service.tick(NOW + timedelta(days=1)) == 1
    delete = await accept_task_control_run(store, "删除任务 " + str(task["id"])[:8], 4)
    await service.apply(
        delete,
        TaskPlan(action="delete", target=str(task["id"])[:8]),
        "delete",
        NOW,
    )
    await store.finish(delete["id"], "completed", "deleted")
    assert await store.claim_run(background=True) is None
    assert await service.tick(NOW + timedelta(days=2)) == 0


async def test_reply_targeted_update_is_scoped_and_ambiguous_delete_changes_nothing(
    store: Any,
) -> None:
    first = await create_task(store)
    second = await create_task(store, 2)
    await store.execute(
        "INSERT INTO kestri.messages(chat_id,telegram_id,direction,content,task_id) "
        "VALUES (111,100,'out','agreement',%s)",
        (first["id"],),
    )
    row = await accept_task_control_run(
        store,
        "把这份简报改短一点",
        3,
        100,
    )
    await TaskService(store, research_settings()).apply(
        row,
        TaskPlan(action="update", instructions="短一点"),
        "update",
        NOW,
    )
    await store.finish(row["id"], "completed", "updated")
    assert (
        "短一点"
        in (await store.one("SELECT instructions FROM kestri.tasks WHERE id=%s", (first["id"],)))[
            "instructions"
        ]
    )
    assert (await store.one("SELECT instructions FROM kestri.tasks WHERE id=%s", (second["id"],)))[
        "instructions"
    ] == "AI 新闻简报"
    time_change = await accept_task_control_run(
        store,
        "把这份简报改到 09:00",
        4,
        100,
    )
    await TaskService(store, research_settings()).apply(
        time_change,
        TaskPlan(action="update", local_time="09:00"),
        "update",
        NOW,
    )
    await store.finish(time_change["id"], "completed", "time updated")
    assert (await store.one("SELECT local_time FROM kestri.tasks WHERE id=%s", (first["id"],)))[
        "local_time"
    ] == "09:00"
    assert (await store.one("SELECT local_time FROM kestri.tasks WHERE id=%s", (second["id"],)))[
        "local_time"
    ] == TIME
    row = await accept_task_control_run(store, "删除任务", 5)
    notice = await TaskService(store, research_settings()).apply(
        row,
        TaskPlan(action="delete"),
        "delete",
        NOW,
    )
    assert "不明确" in notice
    assert len(await store.all("SELECT * FROM kestri.tasks WHERE status='active'")) == 2


async def test_background_is_independent_and_unqualified_stop_targets_foreground(
    store: Any,
) -> None:
    await create_task(store)
    await TaskService(store, research_settings()).tick(NOW)
    background = await store.claim_run(background=True)
    await store.accept(
        2,
        111,
        2,
        "hello",
        None,
        None,
        8,
    )
    foreground = await store.claim_run()
    assert background and foreground
    await store.accept(
        3,
        111,
        3,
        "/stop",
        None,
        "stop",
        8,
    )
    assert await store.cancelled(foreground["id"])
    assert not await store.cancelled(background["id"])
    await store.accept(
        4,
        111,
        4,
        "/stop " + background["id"][:8],
        None,
        "stop",
        8,
    )
    assert await store.cancelled(background["id"])


async def test_transient_retry_bounded_fresh_context_and_saved_result_delivery(
    store: Any,
) -> None:
    await create_task(store)
    await TaskService(store, research_settings()).tick(NOW)
    first = await store.claim_run(background=True)
    assert first
    await store.finish(
        first["id"],
        "failed",
        "temporary",
        "APIConnectionError",
    )
    retry = await store.one("SELECT * FROM kestri.runs WHERE id=%s", (first["id"],))
    assert retry["status"] == "queued" and retry["attempt"] == 2
    assert not await store.all("SELECT * FROM kestri.outbox WHERE run_id=%s", (first["id"],))
    await store.execute("UPDATE kestri.runs SET available_at=now() WHERE id=%s", (first["id"],))
    second = await store.claim_run(background=True)
    assert second and second["source_thread"] is None
    await store.finish(
        second["id"],
        "failed",
        "terminal",
        "APIConnectionError",
    )
    assert (await store.one("SELECT status FROM kestri.runs WHERE id=%s", (second["id"],)))[
        "status"
    ] == "failed"
    assert len(await store.all("SELECT * FROM kestri.outbox WHERE run_id=%s", (second["id"],))) == 1


async def test_task_planner_actual_langchain_serialization_has_no_research_tools(
    store: Any,
) -> None:
    row = await accept_task_control_run(store, REQUEST, 1)
    requests = []
    plan = TaskPlan(
        action="create",
        title="AI",
        instructions="AI 新闻简报",
        local_time=TIME,
        timezone="UTC",
        weekdays=list(range(7)),
    )
    model, async_client, sync_client = offline_model(
        [model_tool_call("TaskPlan", plan.model_dump(), "proposal")], requests
    )
    try:
        await TaskAgent(research_settings(), store, model).run(row, RunControl(store, row["id"]))
    finally:
        await async_client.aclose()
        sync_client.close()
    assert [item["function"]["name"] for item in requests[0]["tools"]] == ["TaskPlan"]
    assert len(await store.all("SELECT * FROM kestri.tasks")) == 1
    assert (await store.one("SELECT status FROM kestri.runs WHERE id=%s", (row["id"],)))[
        "status"
    ] == "completed"


async def test_unauthorized_and_forwarded_requests_cannot_manage_tasks(
    store: Any,
) -> None:
    async with httpx.AsyncClient() as client:
        application = make_application(store, client)
        assert not await application.accept_update(telegram_update(text=REQUEST, user_id=222))
        forwarded = telegram_update(text=REQUEST)
        forwarded["message"]["forward_origin"] = {"type": "channel"}
        assert await application.accept_update(forwarded)
    assert (await store.one("SELECT kind FROM kestri.runs"))["kind"] == "foreground"
    assert not await store.all("SELECT * FROM kestri.tasks")


async def test_background_worker_does_not_block_foreground_and_new_keeps_task(
    store: Any,
) -> None:
    await create_task(store)
    await TaskService(store, research_settings()).tick(NOW)
    started = asyncio.Event()
    release = asyncio.Event()

    class ParallelResearch:
        async def run(self, row: dict, control: RunControl) -> None:
            if row["kind"] == "background":
                started.set()
                await release.wait()
            await store.finish(row["id"], "completed", "done")

    async with httpx.AsyncClient() as client:
        application = make_application(store, client, ParallelResearch())
        background = asyncio.create_task(application.work_once(background=True))
        await asyncio.wait_for(started.wait(), 1)
        assert await application.accept_update(
            telegram_update(text="hello", update_id=2, message_id=2)
        )
        assert await asyncio.wait_for(application.work_once(), 1)
        conversation = await store.one(
            "SELECT thread_id FROM kestri.conversations WHERE chat_id=111"
        )
        assert conversation["thread_id"]
        assert await application.accept_update(
            telegram_update(text="/new", update_id=3, message_id=3)
        )
        assert (await store.one("SELECT thread_id FROM kestri.conversations WHERE chat_id=111"))[
            "thread_id"
        ] is None
        release.set()
        await background
    assert (await store.one("SELECT thread_id FROM kestri.conversations WHERE chat_id=111"))[
        "thread_id"
    ] is None
    assert len(await store.all("SELECT * FROM kestri.tasks WHERE status='active'")) == 1


async def test_stale_queued_occurrence_is_replaced_by_one_eligible_catchup(
    store: Any,
) -> None:
    task = await create_task(store)
    service = TaskService(store, research_settings())
    assert await service.tick(NOW) == 1
    assert await service.tick(NOW + timedelta(days=2)) == 1
    rows = await store.all(
        "SELECT * FROM kestri.runs WHERE task_id=%s AND kind='background' ORDER BY scheduled_for",
        (task["id"],),
    )
    assert [row["status"] for row in rows] == ["cancelled", "queued"]
    assert rows[0]["error_type"] == "CatchUpExpired"
    assert rows[1]["scheduled_for"].date() == (NOW + timedelta(days=2)).date()


async def test_cancel_after_committed_change_reports_agreement_and_no_duplicate(
    store: Any,
) -> None:
    row = await accept_task_control_run(store, REQUEST, 1)
    plan = TaskPlan(
        action="create",
        instructions="AI 新闻简报",
        local_time=TIME,
        timezone="UTC",
        weekdays=list(range(7)),
    )
    notice = await TaskService(store, research_settings()).apply(row, plan, "create")
    await store.execute("UPDATE kestri.runs SET cancel_requested=true WHERE id=%s", (row["id"],))
    await store.finish(
        row["id"],
        "cancelled",
        "stopped",
        "Cancelled",
    )
    record = await store.one("SELECT * FROM kestri.runs WHERE id=%s", (row["id"],))
    assert record["status"] == "completed" and record["result"] == notice
    assert len(await store.all("SELECT * FROM kestri.tasks")) == 1


@pytest.mark.parametrize("text", ["每天 UTC 给我 AI 新闻简报", "每周 08:00 UTC 给我 AI 新闻简报"])
async def test_model_cannot_invent_missing_schedule(store: Any, text: str) -> None:
    row = await accept_task_control_run(store, text, 1)
    notice = await TaskService(store, research_settings()).apply(
        row,
        TaskPlan(
            action="create",
            instructions="AI 新闻简报",
            local_time="08:00",
            timezone="UTC",
            weekdays=list(range(7)),
        ),
        "create",
    )
    assert "尚未创建" in notice
    assert not await store.all("SELECT * FROM kestri.tasks")


async def test_model_cannot_select_an_unmentioned_task(store: Any) -> None:
    first = await create_task(store)
    second = await create_task(store, 2)
    row = await accept_task_control_run(store, "暂停任务 " + str(first["id"])[:8], 3)
    with pytest.raises(PolicyDenied, match="TargetMustComeFromOwner"):
        await TaskService(store, research_settings()).apply(
            row, TaskPlan(action="pause", target=str(second["id"])[:8]), "pause"
        )
    assert all(t["status"] == "active" for t in await store.all("SELECT * FROM kestri.tasks"))


async def test_background_saved_delivery_retry_and_uncertainty_survive_recovery(
    store: Any,
) -> None:
    task = await create_task(store)
    # Dispose only of pending mock control acknowledgements to isolate the briefing outbox.
    await store.execute("UPDATE kestri.outbox SET status='sent'")
    assert await TaskService(store, research_settings()).tick(NOW) == 1
    run = await store.claim_run(background=True)
    await store.finish(run["id"], "completed", "Saved briefing")
    first = await store.claim_delivery()
    assert first["task_id"] == task["id"] and first["reply_to"] is None
    await store.delivery_failed(
        first,
        "RateLimited",
        uncertain=False,
        delay=1,
    )
    await store.recover()
    await store.execute("UPDATE kestri.outbox SET next_attempt=now() WHERE status='pending'")
    retry = await store.claim_delivery()
    assert retry["content"] == first["content"] and retry["id"] == first["id"]
    assert retry["attempts"] == 2
    await store.delivery_failed(retry, "ReadTimeout", uncertain=True)
    await store.recover()
    assert await store.claim_delivery() is None
    assert (await store.one("SELECT status FROM kestri.outbox WHERE id=%s", (first["id"],)))[
        "status"
    ] == "uncertain"
    saved = await store.one("SELECT * FROM kestri.runs WHERE id=%s", (run["id"],))
    assert saved["status"] == "completed" and saved["result"] == first["content"]
    assert len(await store.all("SELECT * FROM kestri.runs WHERE kind='background'")) == 1
