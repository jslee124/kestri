import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from psycopg.errors import CheckViolation

from kestri.errors import BudgetExceeded, PolicyDenied
from kestri.memory.extractor import MemoryProposal, validate_proposal
from kestri.memory.repository import MemoryRepository
from kestri.memory.service import MemoryService
from kestri.memory.worker import MemoryBudget, MemoryJobControl, MemoryWorker
from kestri.storage.lifecycle import TABLES, DataService, encoded, read_private, write_private
from kestri.storage.workspace import Workspace
from tests.helpers import (
    TEST_DSN,
    accept_memory_control_run,
    model_tool_call,
    offline_model,
    research_settings,
)
from tests.memory.helpers import TEXT, enable, enqueue, proposal

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="Set a dedicated KESTRI_TEST_DATABASE_URL")


async def test_default_off_atomic_enable_and_provenance(store: Any) -> None:
    await enqueue(store)
    assert not await store.all("SELECT * FROM kestri.memory_jobs")
    await enable(store, 3)
    await enqueue(store, 4, provenance="forwarded")
    assert not await store.all("SELECT * FROM kestri.memory_jobs")
    await enqueue(store, 5)
    rows = await store.all("SELECT * FROM kestri.memory_jobs")
    assert len(rows) == 1
    assert not (await store.accept(5, 111, 5, TEXT, None, None, 8))[0]
    assert len(await store.all("SELECT * FROM kestri.memory_jobs")) == 1
    assert (await store.one("SELECT provenance FROM kestri.messages WHERE telegram_id=4"))[
        "provenance"
    ] == "forwarded"
    # A forwarded control cannot disable the feature.
    await store.accept(6, 111, 6, "/memory auto off", None, "memory", 8, provenance="forwarded")
    assert (await store.one("SELECT auto_memory_enabled FROM kestri.conversations"))[
        "auto_memory_enabled"
    ]


async def test_foreground_priority_single_lane_and_transactional_publish(store: Any) -> None:
    await enable(store)
    await store.accept(2, 111, 2, TEXT, None, None, 8)
    repo = MemoryRepository(store, research_settings())
    assert await repo.claim(111) is None
    run = await store.claim_run()
    await store.finish(run["id"], "completed", "done")
    claims = await asyncio.gather(repo.claim(111), repo.claim(111))
    job = next(j for j in claims if j is not None)
    assert sum(j is not None for j in claims) == 1
    snapshot = await repo.snapshot(job)
    state = await store.one("SELECT * FROM kestri.conversations")
    validated = validate_proposal(snapshot, proposal(snapshot), store.redactor)
    assert await repo.publish(job, validated) == 1
    memory = await store.one("SELECT * FROM kestri.memories")
    assert memory["origin"] == "auto_direct" and memory["source_message_id"] == 2
    assert len(await store.all("SELECT * FROM kestri.memory_sources")) == 1
    assert len(await store.all("SELECT * FROM kestri.memory_events")) == 1
    new_state = await store.one("SELECT * FROM kestri.conversations")
    assert new_state["thread_id"] == state["thread_id"]
    assert new_state["memory_epoch"] == state["memory_epoch"]
    assert new_state["memory_revision"] == state["memory_revision"] + 1
    with pytest.raises(PolicyDenied):
        await repo.publish(job, validated)
    assert len(await store.all("SELECT * FROM kestri.memories")) == 1
    await store.open()  # All repeated migrations preserve new states/tables.


async def test_candidates_stay_out_of_context_and_survive_migration(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    result = validate_proposal(
        snap, proposal(snap, action="candidate", basis="inference"), store.redactor
    )
    await repo.publish(job, result)
    assert not await MemoryService(store, research_settings()).retrieve(
        {"chat_id": 111, "request": "求职"}
    )
    await store.open()
    assert (await store.one("SELECT status FROM kestri.memories"))["status"] == "candidate"


async def test_off_and_reenable_reject_inflight_and_skip_old_sources(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    await enable(store, 3, False)
    with pytest.raises(PolicyDenied):
        await repo.publish(job, validate_proposal(snap, proposal(snap), store.redactor))
    await enable(store, 4)
    assert await repo.claim(111) is None
    assert not await store.all("SELECT * FROM kestri.memories")
    await enqueue(store, 5)
    new_job = await repo.claim(111)
    new_snapshot = await repo.snapshot(new_job)
    assert all(s.message_id > snap.sources[-1].message_id for s in new_snapshot.sources)


async def test_expired_lease_reclaim_cannot_publish_old_result(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings())
    old = await repo.claim(111)
    snap = await repo.snapshot(old)
    await store.execute("UPDATE kestri.memory_jobs SET lease_until=now()-interval '1 second'")
    new = await repo.claim(111)
    assert new["lease_token"] != old["lease_token"] and new["run_id"] == old["run_id"]
    with pytest.raises(PolicyDenied):
        await repo.publish(old, validate_proposal(snap, proposal(snap), store.redactor))
    await repo.fail(old, "OldWorkerFailure")
    await repo.ensure_active(new)
    await repo.fail(new, "Transient", retry=True)
    await store.execute("UPDATE kestri.memory_jobs SET available_at=now()")
    third = await repo.claim(111)
    assert third["attempts"] == 3
    await repo.fail(third, "Transient", retry=True)
    assert (await store.one("SELECT status FROM kestri.memory_jobs"))["status"] == "failed"


async def test_explicit_correction_and_forget_gate_old_jobs(store: Any) -> None:
    await enable(store)
    row = await accept_memory_control_run(store, "/remember 求职目标", 2)
    service = MemoryService(store, research_settings())
    await service.apply(row)
    await store.finish(row["id"], "completed", "saved")
    await enqueue(store, 3)
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    memory = await store.one("SELECT * FROM kestri.memories")
    row = await accept_memory_control_run(store, "/forget " + str(memory["id"])[:8], 4)
    await service.apply(row)
    await store.finish(row["id"], "completed", "forgotten")
    with pytest.raises(PolicyDenied):
        await repo.publish(job, validate_proposal(snap, proposal(snap), store.redactor))
    await repo.fail(job, "MemoryJobChanged", retry=True)
    await store.execute("UPDATE kestri.memory_jobs SET available_at=now()")
    assert await repo.claim(111) is None
    await enqueue(store, 5)
    new_job = await repo.claim(111)
    new_snapshot = await repo.snapshot(new_job)
    floor = (await store.one("SELECT automatic_history_floor FROM kestri.conversations"))[
        "automatic_history_floor"
    ]
    assert all(s.message_id > floor for s in new_snapshot.sources)


async def test_worker_full_mock_path_accounting_and_restart(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    await store.execute("UPDATE kestri.memory_jobs SET lease_until=now()-interval '1 second'")
    requests = []
    model, ac, sc = offline_model(
        [model_tool_call("MemoryProposal", proposal(snap).model_dump(mode="json"), "memory-1")],
        requests,
    )
    try:
        await store.recover()
        assert await MemoryWorker(store, research_settings(), model).work_once(111)
    finally:
        await ac.aclose()
        sc.close()
    assert len(requests) == 1
    assert requests[0]["max_tokens"] <= 2048
    assert (await store.one("SELECT status FROM kestri.memory_jobs"))["status"] == "succeeded"
    assert (await store.one("SELECT state,kind FROM kestri.usage WHERE kind='memory_extract'")) == {
        "state": "recorded",
        "kind": "memory_extract",
    }
    assert not await repo.claim(111)


async def test_maintenance_budget_and_disabled_reservation(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    control = MemoryJobControl(repo, job)
    budget = MemoryBudget(research_settings(), control)
    await budget.reserve("model", 149999)
    with pytest.raises(BudgetExceeded):
        await budget.reserve("model", 2)
    await enable(store, 3, False)
    with pytest.raises(PolicyDenied):
        await budget.reserve("model", 1)
    assert len(await store.all("SELECT * FROM kestri.usage")) == 1


async def test_backup_quarantines_candidates_and_cancels_jobs(store: Any, tmp_path: Path) -> None:
    await store.bind_identity(123, 111)
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    await repo.publish(
        job,
        validate_proposal(
            snap, proposal(snap, action="candidate", basis="inference"), store.redactor
        ),
    )
    await enqueue(store, 3)
    service = DataService(store, Workspace(tmp_path / "source"), research_settings())
    backup = await service.backup(tmp_path / "backup.json")
    # Disposable fixture DB only: clear rows in reverse dependency order.
    await store.execute("TRUNCATE " + ",".join("kestri." + table for table in TABLES) + " CASCADE")
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        exists = await store.one("SELECT to_regclass(%s) AS name", (f"public.{table}",))
        if exists["name"]:
            await store.execute(f"DELETE FROM public.{table}")
    restored = DataService(store, Workspace(tmp_path / "restored"), research_settings())
    await restored.restore(backup, apply=True)
    assert not (await store.one("SELECT auto_memory_enabled FROM kestri.conversations"))[
        "auto_memory_enabled"
    ]
    assert (await store.one("SELECT status FROM kestri.memories"))["status"] == "quarantined"
    assert not await store.all(
        "SELECT * FROM kestri.memory_jobs WHERE status IN ('queued','running','retry_wait')"
    )
    assert await repo.claim(111) is None


async def test_cleanup_removes_source_excerpts_and_invalidates_auto_facts(
    store: Any, tmp_path: Path
) -> None:
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    await repo.publish(job, validate_proposal(snap, proposal(snap), store.redactor))
    await store.execute("UPDATE kestri.outbox SET status='sent'")
    await store.execute(
        "UPDATE kestri.messages SET created_at=%s", (datetime.now(UTC) - timedelta(days=100),)
    )
    service = DataService(store, Workspace(tmp_path), research_settings())
    report = await service.cleanup(apply=True)
    assert not report["deferred"]
    assert not await store.all("SELECT * FROM kestri.memory_sources")
    assert (await store.one("SELECT status FROM kestri.memories"))["status"] == "expired"
    assert not await MemoryService(store, research_settings()).retrieve(
        {"chat_id": 111, "request": "求职"}
    )


async def test_reinforce_then_replace_preserves_source_and_invalidates_head(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    await repo.publish(job, validate_proposal(snap, proposal(snap), store.redactor))
    original = await store.one("SELECT * FROM kestri.memories")
    await enqueue(store, 3)
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    state = await store.one("SELECT * FROM kestri.conversations")
    reinforcement = proposal(
        snap,
        action="reinforce",
        content=original["content"],
        target_memory_id=original["id"],
        expected_revision=original["revision"],
    )
    await repo.publish(job, validate_proposal(snap, reinforcement, store.redactor))
    reinforced = await store.one("SELECT * FROM kestri.memories")
    assert reinforced["revision"] == 2
    assert len(await store.all("SELECT * FROM kestri.memory_sources")) == 2
    assert (await store.one("SELECT memory_epoch FROM kestri.conversations"))[
        "memory_epoch"
    ] == state["memory_epoch"]
    await enqueue(store, 4, "我现在希望 Kestri 帮助学习英语。")
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    replacement = proposal(
        snap,
        action="replace",
        content="希望 Kestri 帮助学习英语",
        target_memory_id=original["id"],
        expected_revision=2,
    )
    await repo.publish(job, validate_proposal(snap, replacement, store.redactor))
    assert (await store.one("SELECT status FROM kestri.memories WHERE id=%s", (original["id"],)))[
        "status"
    ] == "superseded"
    state2 = await store.one("SELECT * FROM kestri.conversations")
    assert state2["thread_id"] is None and state2["memory_epoch"] == state["memory_epoch"] + 1


async def test_candidate_confirmation_and_forgetting(store: Any) -> None:
    await enable(store)
    repo = MemoryRepository(store, research_settings())
    service = MemoryService(store, research_settings())
    for identity, action in ((2, "correct"), (4, "forget")):
        await enqueue(store, identity)
        job = await repo.claim(111)
        snap = await repo.snapshot(job)
        await repo.publish(
            job,
            validate_proposal(
                snap, proposal(snap, action="candidate", basis="inference"), store.redactor
            ),
        )
        memory = await store.one("SELECT * FROM kestri.memories WHERE status='candidate'")
        text = "/" + action + " " + str(memory["id"])[:8]
        if action == "correct":
            text += " 我确实需要求职帮助"
        run = await accept_memory_control_run(store, text, identity + 1)
        notice = await service.apply(run)
        assert "未作变更" not in notice
        await store.finish(run["id"], "completed", notice)
    assert not await store.all("SELECT * FROM kestri.memories WHERE status='candidate'")
    assert (await store.one("SELECT origin FROM kestri.memories WHERE status='active'"))[
        "origin"
    ] == "explicit_command"
    await store.accept(6, 111, 6, "/memory changes", None, "memory", 8)
    assert (
        "最近的记忆变化"
        in (await store.one("SELECT content FROM kestri.outbox WHERE reply_to=6"))["content"]
    )


async def test_explicit_correction_race_rebuilds_existing_snapshot(store: Any) -> None:
    await enable(store)
    service = MemoryService(store, research_settings())
    run = await accept_memory_control_run(store, "/remember 求职目标", 2)
    await service.apply(run)
    await store.finish(run["id"], "completed", "saved")
    original = await store.one("SELECT * FROM kestri.memories")
    await enqueue(store, 3)
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    run = await accept_memory_control_run(
        store, "/correct " + str(original["id"])[:8] + " 学习英语目标", 4
    )
    await service.apply(run)
    await store.finish(run["id"], "completed", "corrected")
    with pytest.raises(PolicyDenied):
        await repo.publish(job, validate_proposal(snap, proposal(snap), store.redactor))
    await repo.fail(job, "MemoryJobChanged", retry=True)
    await store.execute("UPDATE kestri.memory_jobs SET available_at=now()")
    rebuilt = await repo.snapshot(await repo.claim(111))
    assert rebuilt.memory_revision > snap.memory_revision
    assert all(m.id != original["id"] for m in rebuilt.existing)


async def test_legacy_schema4_restore_explicit_defaults(store: Any, tmp_path: Path) -> None:
    await store.bind_identity(123, 111)
    run = await accept_memory_control_run(store, "/remember 回答使用中文", 1)
    await MemoryService(store, research_settings()).apply(run)
    await store.finish(run["id"], "completed", "saved")
    service = DataService(store, Workspace(tmp_path / "source"), research_settings())
    backup = await service.backup(tmp_path / "backup.json")
    payload = read_private(backup)
    payload["schema"] = 4
    del payload["tables"]["image_inputs"]
    del payload["image_bytes"]
    for row in payload["tables"]["runs"]:
        del row["media_group_id"]
    for name in (
        "memory_jobs",
        "memory_sources",
        "memory_events",
        "memory_index_jobs",
        "history_index_jobs",
    ):
        del payload["tables"][name]
    columns = {
        "conversations": (
            "auto_memory_enabled",
            "memory_revision",
            "memory_settings_generation",
            "memory_activation_watermark",
            "automatic_history_floor",
            "memory_use_enabled",
            "memory_semantic_enabled",
            "memory_retrieval_generation",
            "memory_embedding_space",
            "memory_choice",
        ),
        "outbox": ("presentation",),
        "messages": ("provenance",),
        "memories": (
            "category",
            "origin",
            "revision",
            "fact_key",
            "valid_from",
            "review_after",
            "last_source_message_id",
        ),
    }
    for name, fields in columns.items():
        for row in payload["tables"][name]:
            for field in fields:
                del row[field]
    legacy = tmp_path / "legacy.json"
    write_private(
        legacy,
        encoded({"payload": payload, "sha256": hashlib.sha256(encoded(payload)).hexdigest()}),
    )
    await store.execute("TRUNCATE " + ",".join("kestri." + table for table in TABLES) + " CASCADE")
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        exists = await store.one("SELECT to_regclass(%s) AS name", (f"public.{table}",))
        if exists["name"]:
            await store.execute(f"DELETE FROM public.{table}")
    await DataService(store, Workspace(tmp_path / "restored"), research_settings()).restore(
        legacy, apply=True
    )
    assert (await store.one("SELECT origin,status FROM kestri.memories")) == {
        "origin": "explicit_command",
        "status": "quarantined",
    }
    assert not (await store.one("SELECT auto_memory_enabled FROM kestri.conversations"))[
        "auto_memory_enabled"
    ]


async def test_enqueue_failure_rolls_back_archive_and_acceptance(store: Any) -> None:
    await enable(store)
    await store.execute(
        "ALTER TABLE kestri.memory_jobs ADD CONSTRAINT test_refusal CHECK(false) NOT VALID"
    )
    with pytest.raises(CheckViolation):
        await store.accept(2, 111, 2, TEXT, None, None, 8)
    assert not await store.all("SELECT * FROM kestri.inbox WHERE update_id=2")
    assert not await store.all("SELECT * FROM kestri.messages WHERE telegram_id=2")
    assert not await store.all("SELECT * FROM kestri.runs WHERE message_id=2")
    await store.execute("ALTER TABLE kestri.memory_jobs DROP CONSTRAINT test_refusal")
    await enqueue(store)
    assert len(await store.all("SELECT * FROM kestri.memory_jobs")) == 1


async def test_capacity_failure_is_atomic_and_review_expiry_resets_context(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings(auto_memory_limit=1))
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    first = proposal(snap)
    second = proposal(snap, content="求职是当前目标", fact_key="career.goal")
    operations = MemoryProposal(operations=[first.operations[0], second.operations[0]])
    with pytest.raises(PolicyDenied):
        await repo.publish(job, validate_proposal(snap, operations, store.redactor))
    assert not await store.all("SELECT * FROM kestri.memories")
    assert not await store.all("SELECT * FROM kestri.memory_sources")
    assert not await store.all("SELECT * FROM kestri.memory_events")
    await repo.publish(job, validate_proposal(snap, first, store.redactor))
    epoch = (await store.one("SELECT memory_epoch FROM kestri.conversations"))["memory_epoch"]
    await store.execute("UPDATE kestri.memories SET review_after=now()-interval '1 second'")
    await MemoryService(store, research_settings()).expire(111)
    assert (await store.one("SELECT status FROM kestri.memories"))["status"] == "expired"
    assert (await store.one("SELECT memory_epoch,thread_id FROM kestri.conversations")) == {
        "memory_epoch": epoch + 1,
        "thread_id": None,
    }


async def test_monthly_cap_and_reclaimed_unknown_reservations(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    settings = research_settings(memory_maintenance_monthly_usd="0.10")
    budget = MemoryBudget(settings, MemoryJobControl(repo, job))
    await budget.reserve("model", 100000)
    with pytest.raises(BudgetExceeded):
        await budget.reserve("model", 1)
    await store.execute("UPDATE kestri.memory_jobs SET lease_until=now()-interval '1 second'")
    new_job = await repo.claim(111)
    assert (await store.one("SELECT state FROM kestri.usage"))["state"] == "unknown"
    new_budget = MemoryBudget(settings, MemoryJobControl(repo, new_job))
    with pytest.raises(BudgetExceeded):
        await new_budget.reserve("model", 1)
    assert len(await store.all("SELECT * FROM kestri.usage")) == 1


async def test_large_candidate_inspection_is_bounded_and_paginated(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings())
    job = await repo.claim(111)
    snap = await repo.snapshot(job)
    base = proposal(snap, action="candidate", basis="inference")
    operations = MemoryProposal(
        operations=[
            base.operations[0].model_copy(update={"content": str(i) + "待主人确认的推断" * 120})
            for i in range(6)
        ]
    )
    await repo.publish(job, validate_proposal(snap, operations, store.redactor))
    await store.accept(3, 111, 3, "/memory pending", None, "memory", 8)
    chunks = await store.all("SELECT content FROM kestri.outbox WHERE reply_to=3 ORDER BY sequence")
    assert len(chunks) == 1 and len(chunks[0]["content"]) <= 3500
    assert "下一页：/memory pending 1" in chunks[0]["content"]
    await store.accept(4, 111, 4, "/memory pending 1", None, "memory", 8)
    next_page = await store.one("SELECT content FROM kestri.outbox WHERE reply_to=4")
    assert "第 2 页" in next_page["content"] and "下一页" not in next_page["content"]
    assert chunks[0]["content"].count("编号：") == 5
    assert next_page["content"].count("编号：") == 1


async def test_crashed_final_attempt_cancels_and_preserves_unknown_cost(store: Any) -> None:
    await enable(store)
    await enqueue(store)
    repo = MemoryRepository(store, research_settings())
    for attempt in range(1, 4):
        job = await repo.claim(111)
        assert job["attempts"] == attempt
        await MemoryBudget(research_settings(), MemoryJobControl(repo, job)).reserve("model", 1000)
        await store.execute("UPDATE kestri.memory_jobs SET lease_until=now()-interval '1 second'")
    assert await repo.claim(111) is None
    assert (await store.one("SELECT status FROM kestri.memory_jobs"))["status"] == "cancelled"
    usage = await store.all("SELECT state,amount_micro_usd FROM kestri.usage")
    assert len(usage) == 3 and all(
        r == {"state": "unknown", "amount_micro_usd": 1000} for r in usage
    )


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("InvalidMemorySource", "InvalidMemorySource"),
        ("private arbitrary provider body", "PolicyRejected"),
    ],
)
async def test_policy_failure_retains_only_known_static_reason(
    store: Any, reason: str, expected: str
) -> None:
    await enable(store)
    await enqueue(store)

    class RejectedExtractor:
        async def extract(self, *args: Any) -> Any:
            raise PolicyDenied(reason)

    worker = MemoryWorker(store, research_settings(), cast(Any, object()))
    worker.extractor = cast(Any, RejectedExtractor())
    assert await worker.work_once(111)
    job = await store.one("SELECT * FROM kestri.memory_jobs")
    assert job["status"] == "failed"
    assert job["error_type"] == expected
    assert await store.one("SELECT id FROM kestri.memories") is None


async def test_source_annotation_retries_are_bounded_and_never_publish(store: Any) -> None:
    await enable(store)
    await enqueue(store)

    class BadAnnotationExtractor:
        async def extract(self, *args: Any) -> Any:
            raise PolicyDenied("InvalidMemorySourceOffset")

    worker = MemoryWorker(store, research_settings(), cast(Any, object()))
    worker.extractor = cast(Any, BadAnnotationExtractor())
    for attempt in range(1, 4):
        assert await worker.work_once(111)
        job = await store.one("SELECT * FROM kestri.memory_jobs")
        assert job["attempts"] == attempt
        assert job["status"] == ("retry_wait" if attempt < 3 else "failed")
        assert job["error_type"] == "InvalidMemorySourceOffset"
        assert await store.one("SELECT id FROM kestri.memories") is None
        await store.execute("UPDATE kestri.memory_jobs SET available_at=now()")
    assert not await worker.work_once(111)
