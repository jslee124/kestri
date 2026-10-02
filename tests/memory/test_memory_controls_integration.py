from typing import Any

import pytest

from kestri.memory.extractor import validate_proposal
from kestri.memory.repository import MemoryRepository
from kestri.memory.service import MemoryService
from tests.helpers import (
    TEST_DSN,
    accept_memory_control_run,
    research_settings,
    save_memory,
)
from tests.memory.helpers import enable, enqueue, proposal

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="Set a dedicated KESTRI_TEST_DATABASE_URL")


async def apply_control(store: Any, text: str, identity: int) -> str:
    run = await accept_memory_control_run(store, text, identity)
    result = await MemoryService(store, research_settings()).apply(run)
    await store.finish(run["id"], "completed", result)
    return result


async def test_unique_literal_correction_and_forget(store: Any) -> None:
    original = await save_memory(store, "我的主力语言是 Python。")
    result = await apply_control(store, "把关于Python的记忆改成我的主力语言是 Rust。", 2)
    assert "已保存" in result
    replacement = await store.one("SELECT * FROM kestri.memories WHERE status='active'")
    assert replacement["content"] == "我的主力语言是 Rust"
    assert replacement["supersedes"] == original["id"]
    result = await apply_control(store, "忘记关于Rust的记忆", 3)
    assert "已忘记" in result
    assert not await store.all("SELECT * FROM kestri.memories WHERE status='active'")


async def test_ambiguous_target_suggests_without_writing_then_explicit_selection(
    store: Any,
) -> None:
    first = await save_memory(store, "Python 用于后端。", 1)
    second = await save_memory(store, "Python 用于数据分析。", 2)
    state = await store.one("SELECT memory_epoch FROM kestri.conversations")
    result = await apply_control(store, "忘记关于Python的记忆", 3)
    assert (
        "未作变更" in result and str(first["id"])[:8] in result and str(second["id"])[:8] in result
    )
    assert len(await store.all("SELECT * FROM kestri.memories WHERE status='active'")) == 2
    assert (await store.one("SELECT memory_epoch FROM kestri.conversations")) == state
    assert "已忘记" in await apply_control(store, f"/forget {first['id']}", 4)
    assert (await store.one("SELECT status FROM kestri.memories WHERE id=%s", (second["id"],)))[
        "status"
    ] == "active"


async def test_semantic_similarity_cannot_authorize_target(store: Any) -> None:
    await save_memory(store, "饮食选择清淡不辣。")
    result = await apply_control(store, "忘记关于点菜口味的记忆", 2)
    assert "未作变更" in result
    assert (await store.one("SELECT status FROM kestri.memories"))["status"] == "active"


async def publish(store: Any, **changes: Any) -> tuple[Any, Any]:
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    assert job
    batch = await repo.snapshot(job)
    await repo.publish(job, validate_proposal(batch, proposal(batch, **changes), store.redactor))
    return job, await store.one("SELECT * FROM kestri.memories ORDER BY created_at DESC LIMIT 1")


async def notice(store: Any) -> Any:
    return await store.one(
        "SELECT o.* FROM kestri.outbox o JOIN kestri.runs r ON r.id=o.run_id "
        "WHERE r.kind='memory_maintenance' ORDER BY o.sequence DESC LIMIT 1"
    )


async def test_new_notice_durable_reinforcement_silent_and_delivery_rechecked(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    job, memory = await publish(store)
    row = await notice(store)
    assert row["status"] == "pending" and str(memory["id"])[:8] in row["content"]
    assert str(row["run_id"]) == job["run_id"]
    await store.recover()
    assert await store.delivery_current(row)
    await enqueue(store, 3)
    await publish(
        store,
        action="reinforce",
        content=memory["content"],
        target_memory_id=str(memory["id"]),
        expected_revision=memory["revision"],
    )
    assert (await notice(store))["id"] == row["id"]
    await enable(store, 4, enabled=False)
    assert not await store.delivery_current(row)
    cancelled = await notice(store)
    assert cancelled["status"] == "failed" and cancelled["content"] == ""


@pytest.mark.parametrize("control", ["forget", "use", "semantic"])
async def test_stale_notice_suppressed_at_claim(store: Any, control: str) -> None:
    await enable(store)
    if control == "semantic":
        await store.execute("UPDATE kestri.conversations SET memory_semantic_enabled=true")
    await enqueue(store)
    _, memory = await publish(store)
    if control == "forget":
        await apply_control(store, f"/forget {memory['id']}", 3)
    else:
        await store.accept(3, 111, 3, f"/memory {control} off", None, "memory", 8)
    # Earlier acknowledgement outbox rows may be claimed first.
    while row := await store.claim_delivery():
        assert row["id"] != (await notice(store))["id"]
        await store.delivered(row, 1000 + row["sequence"])
    assert (await notice(store))["status"] == "failed"


async def test_replacement_notice_uses_new_epoch_and_candidate_is_silent(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    _, old = await publish(store)
    await enqueue(store, 3, text="我现在希望 Kestri 帮助学英语。")
    await publish(
        store,
        action="replace",
        content="希望 Kestri 帮助学英语",
        target_memory_id=str(old["id"]),
        expected_revision=old["revision"],
    )
    latest = await notice(store)
    assert "更新" in latest["content"] and await store.delivery_current(latest)
    await enqueue(store, 4, text="我可能比较适合阅读。")
    await publish(store, action="candidate", basis="inference", content="可能喜欢阅读")
    assert (await notice(store))["id"] == latest["id"]


async def test_legacy_chinese_id_control_remains_available(store: Any) -> None:
    original = await save_memory(store, "用 Python")
    result = await apply_control(store, f"忘记记忆：{original['id']}", 2)
    assert "已忘记" in result
    assert (await store.one("SELECT status FROM kestri.memories"))["status"] == "forgotten"


async def test_hexadecimal_content_target_is_not_an_implicit_uuid(store: Any) -> None:
    first = await save_memory(store, "主力语言是 Go。", 1)
    other_id = "deadbeef-0000-4000-8000-000000000000"
    await store.execute("UPDATE kestri.memories SET id=%s WHERE id=%s", (other_id, first["id"]))
    target = await save_memory(store, "项目名为 deadbeef。", 2)
    assert "已忘记" in await apply_control(store, "忘记关于deadbeef的记忆", 3)
    assert (await store.one("SELECT status FROM kestri.memories WHERE id=%s", (other_id,)))[
        "status"
    ] == "active"
    assert (await store.one("SELECT status FROM kestri.memories WHERE id=%s", (target["id"],)))[
        "status"
    ] == "forgotten"
