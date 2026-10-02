import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from kestri.data import DataService, encoded, read_private, write_private
from kestri.errors import PolicyDenied
from kestri.memory import MemoryService
from kestri.tasks import TaskPlan, TaskService
from kestri.workspace import Workspace

from . import test_m1
from .test_m1 import TEST_DSN, settings
from .test_m2 import NOW, control_run, create
from .test_m3 import memory_run, remember
from .test_runtime import offline_model

base_store = test_m1.store
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="Set a dedicated KESTRI_TEST_DATABASE_URL")


@pytest.fixture
async def store(base_store: Any) -> Any:
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        exists = await base_store.one("SELECT to_regclass(%s) AS name", (f"public.{table}",))
        if exists["name"]:
            await base_store.execute(f"DELETE FROM public.{table}")
    await base_store.bind_identity(123, 111)
    return base_store


async def seed(store: Any, root: Path) -> tuple[DataService, dict, dict, str]:
    service = DataService(store, Workspace(root), settings())
    task = await create(store)
    memory = await remember(store, "回答使用中文", 2)
    run = await test_m1.accept_run(store, "Public research", 3)
    evidence_id = str(uuid4())
    service.workspace.write(run["id"], evidence_id, "Public source facts")
    await store.add_evidence(
        run["id"],
        "extracted_page",
        "https://example.com",
        "Source",
        "retrieved",
        False,
        {},
        evidence_id,
    )
    reservation = await store.reserve(str(run["id"]), "model", 100, 1_000_000, 1_000_000)
    await store.settle(reservation, {"fixture": True}, 100)
    await store.finish(run["id"], "completed", "Public answer")
    return service, task, memory, evidence_id


async def fresh_target(store: Any, root: Path) -> DataService:
    await store.execute("DROP SCHEMA kestri CASCADE")
    await store.open()
    return DataService(store, Workspace(root), settings())


async def test_old_backup_roundtrip_quarantines_deleted_memory_tasks_and_replay(
    store: Any, tmp_path: Path
) -> None:
    source, task, memory, evidence_id = await seed(store, tmp_path / "source")
    backup = await source.backup(tmp_path / "backup.json")
    assert backup.stat().st_mode & 0o777 == 0o600
    row = await memory_run(store, "/forget " + str(memory["id"])[:8], 4)
    await MemoryService(store, settings()).apply(row)
    await store.finish(row["id"], "completed", "forgotten")
    row = await control_run(store, "/task 删除 " + str(task["id"])[:8], 5)
    await TaskService(store, settings()).apply(
        row, TaskPlan(action="delete", target=str(task["id"])[:8]), "delete", NOW
    )
    await store.finish(row["id"], "completed", "deleted")
    restored = await fresh_target(store, tmp_path / "restored")
    preview = await restored.restore(backup)
    assert not preview["applied"] and not await store.all("SELECT * FROM kestri.messages")
    report = await restored.restore(backup, apply=True)
    assert report["applied"] and report["evidence_files"] == 1
    assert (await store.one("SELECT status FROM kestri.memories"))["status"] == "quarantined"
    assert not await MemoryService(store, settings()).retrieve({"chat_id": 111, "request": "中文"})
    assert (await store.one("SELECT status,restored FROM kestri.tasks")) == {
        "status": "paused",
        "restored": True,
    }
    assert not await TaskService(store, settings()).tick(NOW + timedelta(days=1))
    assert not await store.claim_delivery()
    assert (await store.one("SELECT thread_id FROM kestri.conversations"))["thread_id"] is None
    evidence = await store.one("SELECT * FROM kestri.evidence WHERE id=%s", (evidence_id,))
    assert (
        restored.workspace.read(str(evidence["run_id"]), evidence_id, 64000)[0]
        == "Public source facts"
    )
    # An explicit owner reauthorization works; no imported schedule resumes on its own.
    row = await control_run(store, "/task 恢复 " + str(task["id"])[:8], 4)
    result = await TaskService(store, settings()).apply(
        row, TaskPlan(action="resume", target=str(task["id"])[:8]), "resume", NOW
    )
    await store.finish(row["id"], "completed", result)
    assert (await store.one("SELECT status,restored FROM kestri.tasks")) == {
        "status": "active",
        "restored": False,
    }
    await remember(store, "回答使用中文", 5)
    assert (
        len(await MemoryService(store, settings()).retrieve({"chat_id": 111, "request": "中文"}))
        == 1
    )


async def test_retention_deletes_copies_checkpoint_and_files_preserving_durable_state(
    store: Any, tmp_path: Path
) -> None:
    service, task, memory, evidence_id = await seed(store, tmp_path)
    run = await store.one("SELECT * FROM kestri.runs WHERE message_id=3")
    saver = AsyncPostgresSaver(store.pool)
    await saver.setup()
    model, ac, sc = offline_model([], [])
    try:
        agent = create_agent(model, tools=[], checkpointer=saver)
        await agent.aupdate_state(
            {"configurable": {"thread_id": str(run["id"])}},
            {"messages": [HumanMessage(content="Old private history")]},
        )
    finally:
        await ac.aclose()
        sc.close()
    now = datetime.now(UTC)
    old = now - timedelta(days=100)
    await store.execute("UPDATE kestri.messages SET created_at=%s", (old,))
    await store.execute("UPDATE kestri.runs SET created_at=%s WHERE id=%s", (old, run["id"]))
    await store.execute("UPDATE kestri.outbox SET status='sent',created_at=%s", (old,))
    await store.execute("UPDATE kestri.evidence SET created_at=%s", (now - timedelta(days=31),))
    await store.event(str(run["id"]), "fixture", {"old": "data"})
    await store.execute("UPDATE kestri.events SET created_at=%s", (old,))
    preview = await service.cleanup(now=now)
    assert preview["messages"] == 3 and preview["evidence"] == 1
    assert await store.all("SELECT * FROM public.checkpoints")
    assert service.workspace.read(str(run["id"]), evidence_id, 64000)[0]
    result = await service.cleanup(apply=True, now=now)
    assert result["applied"]
    assert not await store.all("SELECT * FROM kestri.messages")
    assert not await store.all("SELECT * FROM public.checkpoints")
    assert not await store.all("SELECT * FROM public.checkpoint_blobs")
    assert not await store.all("SELECT * FROM public.checkpoint_writes")
    assert not await store.all("SELECT * FROM kestri.events")
    assert (
        await store.one(
            "SELECT request,result,history_expired FROM kestri.runs WHERE id=%s", (run["id"],)
        )
    ) == {"request": "", "result": None, "history_expired": True}
    assert not (tmp_path / str(run["id"]) / f"{evidence_id}.txt").exists()
    assert (await store.one("SELECT status,url,title FROM kestri.evidence")) == {
        "status": "expired",
        "url": "",
        "title": "",
    }
    assert (await store.one("SELECT status FROM kestri.memories WHERE id=%s", (memory["id"],)))[
        "status"
    ] == "active"
    assert (await store.one("SELECT status FROM kestri.tasks WHERE id=%s", (task["id"],)))[
        "status"
    ] == "active"
    assert not (await service.cleanup(apply=True, now=now))["evidence"]


async def test_erase_content_managed_backup_and_minimal_cost_ledger(
    store: Any, tmp_path: Path
) -> None:
    service, _, _, evidence_id = await seed(store, tmp_path)
    backup = await service.backup()
    unrelated = backup.parent / "operator-notes.txt"
    unrelated.write_text("Keep this unrelated file")
    await store.execute("UPDATE kestri.outbox SET status='sent'")
    run = await store.one("SELECT id FROM kestri.runs WHERE message_id=3")
    report = await service.cleanup(apply=True, erase=True)
    assert report["backup_files"] == 1 and not backup.exists() and unrelated.exists()
    assert not await store.all("SELECT * FROM kestri.messages")
    assert not (tmp_path / str(run["id"]) / f"{evidence_id}.txt").exists()
    assert not await store.all(
        "SELECT * FROM kestri.memories WHERE content!='' OR status!='forgotten'"
    )
    assert not await store.all(
        "SELECT * FROM kestri.tasks WHERE instructions!='' OR status!='deleted'"
    )
    assert not await store.all("SELECT * FROM kestri.runs WHERE request!='' OR result IS NOT NULL")
    assert (await store.one("SELECT sum(amount_micro_usd) AS n FROM kestri.usage"))["n"] == 100
    assert await store.one("SELECT * FROM kestri.meta WHERE key='identity'")


async def test_lease_and_idle_checks_prevent_maintenance_races(store: Any, tmp_path: Path) -> None:
    service, _, _, _ = await seed(store, tmp_path)
    assert (await service.cleanup(apply=True, operator=False))["deferred"]
    async with store.pool.connection() as conn:
        await conn.execute("SELECT pg_advisory_lock(hashtext('kestri-bot-123'))")
        try:
            with pytest.raises(PolicyDenied, match="StopApplicationBeforeMaintenance"):
                await service.backup()
        finally:
            await conn.execute("SELECT pg_advisory_unlock_all()")
    assert not (tmp_path / "backups").exists()


async def test_missing_evidence_nonempty_target_and_export_are_not_silently_restored(
    store: Any, tmp_path: Path
) -> None:
    service, _, _, evidence_id = await seed(store, tmp_path / "source")
    backup = await service.backup(tmp_path / "backup.json")
    with pytest.raises(PolicyDenied, match="RestoreRequiresEmptyDatabase"):
        await service.restore(backup, apply=True)
    export = await service.backup(tmp_path / "export.json", export=True)
    with pytest.raises(PolicyDenied, match="NotRestorableBackup"):
        await service.restore(export)
    evidence = await store.one("SELECT run_id FROM kestri.evidence WHERE id=%s", (evidence_id,))
    service.workspace.remove(str(evidence["run_id"]), evidence_id)
    with pytest.raises(PolicyDenied, match="WorkspaceBoundary"):
        await service.backup(tmp_path / "incomplete.json")
    assert not (tmp_path / "incomplete.json").exists()


async def test_corrupt_private_bundle_and_file_policy_reject_before_mutation(
    store: Any, tmp_path: Path
) -> None:
    service, _, _, _ = await seed(store, tmp_path / "source")
    backup = await service.backup(tmp_path / "backup.json")
    content = json.loads(backup.read_text())
    content["payload"]["schema"] = 999
    corrupt = tmp_path / "corrupt.json"
    write_private(corrupt, encoded(content))
    with pytest.raises(PolicyDenied, match="BackupChecksumMismatch"):
        await service.restore(corrupt, apply=True)
    link = tmp_path / "link.json"
    link.symlink_to(backup)
    with pytest.raises(OSError):
        read_private(link)
    backup.chmod(0o644)
    with pytest.raises(PolicyDenied, match="BackupFilePolicy"):
        read_private(backup)
    assert len(await store.all("SELECT * FROM kestri.memories")) == 1


async def test_restore_file_failure_rolls_back_database_and_new_files(
    store: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, _, _ = await seed(store, tmp_path / "source")
    backup = await service.backup(tmp_path / "backup.json")
    restored = await fresh_target(store, tmp_path / "restored")
    original = restored.workspace.write

    def fail_after_write(*args: Any) -> None:
        original(*args)
        raise OSError("Injected storage failure")

    monkeypatch.setattr(restored.workspace, "write", fail_after_write)
    with pytest.raises(OSError, match="Injected storage"):
        await restored.restore(backup, apply=True)
    assert not await store.all("SELECT * FROM kestri.meta")
    assert not await store.all("SELECT * FROM kestri.memories")
    assert not list(restored.workspace.root.iterdir())


async def test_managed_backup_expiry_preserves_external_copy_and_unrelated_files(
    store: Any, tmp_path: Path
) -> None:
    service, _, _, _ = await seed(store, tmp_path / "source")
    backup = await service.backup()
    external = await service.backup(tmp_path / "external.json")
    old = (datetime.now(UTC) - timedelta(days=31)).timestamp()
    os.utime(backup, (old, old))
    assert service.prune_backups(datetime.now(UTC)) == 1
    assert not backup.exists() and external.exists()


async def test_restored_pending_telegram_commands_are_skipped_once(
    store: Any, tmp_path: Path
) -> None:
    import httpx

    from kestri.application import Application
    from kestri.telegram import TelegramClient

    requests = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": [
                    {
                        "update_id": 999,
                        "message": {"text": "/remember resurrect this", "message_id": 1},
                    }
                ],
            },
        )

    await store.execute(
        "INSERT INTO kestri.meta(key,value) "
        "VALUES ('restore_quarantine','{\"pending_updates\":true}')"
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        application = Application(
            settings(), store, TelegramClient("123:abcdefghijklmnopqrstuvwxyz", client), None
        )
        await application.prepare_restore()
        await application.prepare_restore()
    assert len(requests) == 1 and requests[0]["offset"] == -1 and requests[0]["timeout"] == 0
    assert await store.offset() == 1000
    assert not await store.all("SELECT * FROM kestri.inbox")
    assert not await store.all("SELECT * FROM kestri.memories")
    assert not await store.all("SELECT * FROM kestri.tasks")
    assert len(await store.all("SELECT * FROM kestri.outbox")) == 1


async def test_failed_file_cleanup_is_inaccessible_and_retried(
    store: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, _, evidence_id = await seed(store, tmp_path)
    await store.execute("UPDATE kestri.outbox SET status='sent'")
    await store.execute("UPDATE kestri.evidence SET created_at=now()-interval '31 days'")
    original = service.workspace.remove

    def failure(*args: Any) -> None:
        raise OSError("Injected unlink failure")

    monkeypatch.setattr(service.workspace, "remove", failure)
    with pytest.raises(OSError, match="unlink failure"):
        await service.cleanup(apply=True)
    record = await store.one("SELECT * FROM kestri.evidence WHERE id=%s", (evidence_id,))
    assert record["status"] == "expired" and record["metadata"]["cleanup_pending"]
    monkeypatch.setattr(service.workspace, "remove", original)
    await service.cleanup(apply=True)
    assert (await store.one("SELECT metadata FROM kestri.evidence"))["metadata"] == {}
    assert not (tmp_path / str(record["run_id"]) / f"{evidence_id}.txt").exists()


def test_cleanup_cannot_follow_directory_symlinks(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    run_id, evidence_id = str(uuid4()), str(uuid4())
    outside = tmp_path / "unrelated"
    outside.mkdir()
    target = outside / f"{evidence_id}.txt"
    target.write_text("Keep this file")
    (workspace.root / run_id).symlink_to(outside, target_is_directory=True)
    with pytest.raises(PolicyDenied, match="WorkspaceBoundary"):
        workspace.remove(run_id, evidence_id)
    assert target.read_text() == "Keep this file"


async def test_cancelled_backup_keeps_lease_until_file_worker_finishes(
    store: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio
    from threading import Event

    import kestri.data as data_module

    service, _, _, _ = await seed(store, tmp_path / "source")
    entered, release = Event(), Event()
    original = data_module.write_private

    def blocked_write(path: Path, data: bytes) -> None:
        entered.set()
        assert release.wait(5)
        original(path, data)

    monkeypatch.setattr(data_module, "write_private", blocked_write)
    task = asyncio.create_task(service.backup(tmp_path / "backup.json"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        with pytest.raises(PolicyDenied, match="MaintenanceAlreadyRunning"):
            async with service.exclusive():
                pass
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert read_private(tmp_path / "backup.json")["kind"] == "backup"
