import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from kestri.errors import BudgetExceeded, PolicyDenied
from kestri.history.worker import HistoryIndexBudget, HistoryIndexWorker, HistoryJobControl
from kestri.integrations.embedding import EmbeddingClient
from kestri.memory.embedding import embedding_space
from kestri.storage.lifecycle import TABLES, DataService, encoded, read_private, write_private
from kestri.storage.workspace import Workspace
from tests.helpers import accept_run, research_settings
from tests.history.test_history_integration import enabled, old_turn
from tests.history.test_semantic_history_integration import history, response, settings

V = tuple([1.0] + [0.0] * 1023)


@pytest.fixture
async def configured(store: Any) -> Any:
    if not (await store.one("SELECT to_regclass('kestri.history_embeddings') AS name"))["name"]:
        pytest.skip("Requires pgvector matrix leg")
    await enabled(store)
    store.embedding_space = embedding_space(settings().embedding_config())
    await store.accept(101, 111, 101, "/memory semantic on", None, "memory", 8)
    return store


def worker(store: Any, http: httpx.AsyncClient, options: Any = None) -> HistoryIndexWorker:
    return HistoryIndexWorker(
        store, options or settings(), EmbeddingClient(settings().embedding_config(), http)
    )


async def test_enqueue_foreground_priority_source_revision_and_worker_pipeline(
    configured: Any,
) -> None:
    store = configured
    run = await accept_run(store, "学习智能体", 1)
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        indexer = worker(store, http)
        assert await indexer.claim(111) is None
        assert (await store.one("SELECT status FROM kestri.history_index_jobs"))[
            "status"
        ] == "queued"
        await store.finish(run["id"], "completed", "done")
        assert await indexer.work_once(111)
        job = await store.one("SELECT * FROM kestri.history_index_jobs")
        assert job["status"] == "succeeded" and job["attempts"] == 1
        await store.execute(
            "INSERT INTO kestri.messages(chat_id,direction,content,run_id,provenance) "
            "VALUES (111,'out','助手提案',%s,'context')",
            (run["id"],),
        )
        revised = await store.one("SELECT * FROM kestri.history_index_jobs")
        assert revised["source_revision"] == job["source_revision"] + 1
        assert revised["status"] == "queued" and revised["run_id"] is None
        assert not await store.all("SELECT * FROM kestri.history_embeddings")
        assert await indexer.work_once(111)
        assert len(json.loads(requests[-1]["input"][0])) == 2
        assert (
            await store.one("SELECT state FROM kestri.usage WHERE kind='history_index' LIMIT 1")
        )["state"] == "recorded"


async def test_concurrent_claim_reclaim_and_stale_lease_cannot_bill_or_publish(
    configured: Any,
) -> None:
    store = configured
    await old_turn(store, "学习智能体", 1)
    async with httpx.AsyncClient() as http:
        indexer = worker(store, http)
        claims = await asyncio.gather(indexer.claim(111), indexer.claim(111))
        assert sum(job is not None for job in claims) == 1
        old = next(job for job in claims if job)
        budget = HistoryIndexBudget(settings(), HistoryJobControl(indexer, old))
        reservation = await budget.reserve("test", 1)
        await store.execute(
            "UPDATE kestri.history_index_jobs SET lease_until=now()-interval '1 second'"
        )
        renewed = await indexer.claim(111)
        assert renewed["run_id"] == old["run_id"] and renewed["lease_token"] != old["lease_token"]
        assert (await store.one("SELECT state FROM kestri.usage WHERE id=%s", (reservation,)))[
            "state"
        ] == "unknown"
        with pytest.raises(PolicyDenied):
            await budget.reserve("test", 1)
        with pytest.raises(PolicyDenied):
            await indexer.publish(old, V)
        await indexer.fail(old, "OldLease", retry=True)
        assert (await store.one("SELECT status FROM kestri.history_index_jobs"))[
            "status"
        ] == "running"
        await indexer.publish(renewed, V)
        assert (await store.one("SELECT status FROM kestri.history_index_jobs"))[
            "status"
        ] == "succeeded"


async def test_retry_budget_and_shared_maintenance_cap(configured: Any) -> None:
    store = configured
    await old_turn(store, "学习智能体", 1)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(503))
    ) as http:
        indexer = worker(store, http)
        for _ in range(3):
            await store.execute(
                "UPDATE kestri.history_index_jobs SET available_at=now()-interval '1 second'"
            )
            assert await indexer.work_once(111)
        job = await store.one("SELECT * FROM kestri.history_index_jobs")
        assert job["attempts"] == 3 and job["status"] == "failed"
        assert (
            len(
                await store.all(
                    "SELECT * FROM kestri.usage WHERE state='unknown' AND kind='history_index'"
                )
            )
            == 3
        )
        assert not await indexer.work_once(111)
        await store.execute(
            "UPDATE kestri.messages SET content='学习英语' WHERE direction='in' AND telegram_id=1"
        )
        options = settings().model_copy(
            update={
                "memory_maintenance_monthly_usd": settings().memory_maintenance_monthly_usd / 1000
            }
        )
        indexer = worker(store, http, options)
        job = await indexer.claim(111)
        await store.execute("UPDATE kestri.usage SET kind='memory_extract',amount_micro_usd=400")
        with pytest.raises(BudgetExceeded):
            await HistoryIndexBudget(options, HistoryJobControl(indexer, job)).reserve("test", 600)


@pytest.mark.parametrize("command", ["/memory auto off", "/memory use off", "/memory semantic off"])
async def test_disable_during_history_embedding_blocks_publication(
    configured: Any, command: str
) -> None:
    store = configured
    await old_turn(store, "学习智能体", 1)

    async def respond(request: httpx.Request) -> httpx.Response:
        await store.accept(102, 111, 102, command, None, "memory", 8)
        return response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        assert await worker(store, http).work_once(111)
    assert not await store.all("SELECT * FROM kestri.history_embeddings")
    assert (await store.one("SELECT status FROM kestri.history_index_jobs"))[
        "status"
    ] == "cancelled"
    assert (await store.one("SELECT state FROM kestri.usage WHERE kind='history_index'"))[
        "state"
    ] == "recorded"


async def test_source_delete_and_floor_cancel_jobs_before_rebilling(configured: Any) -> None:
    store = configured
    await old_turn(store, "学习智能体", 1)
    async with httpx.AsyncClient() as http:
        indexer = worker(store, http)
        job = await indexer.claim(111)
        await store.execute("DELETE FROM kestri.messages WHERE id=%s", (job["owner_message_id"],))
        row = await store.one("SELECT * FROM kestri.history_index_jobs")
        assert row["owner_message_id"] is None and row["status"] == "cancelled"
        with pytest.raises(PolicyDenied):
            await indexer.publish(job, V)
        await old_turn(store, "学习英语", 2)
        await store.execute(
            "UPDATE kestri.conversations SET automatic_history_floor=999 WHERE chat_id=111"
        )
        assert not await indexer.work_once(111)
        assert all(
            j["status"] == "cancelled"
            for j in await store.all("SELECT * FROM kestri.history_index_jobs")
        )


async def test_foreground_cache_reuse_and_backup8_legacy6_restore(
    configured: Any, tmp_path: Path
) -> None:
    store = configured
    await store.bind_identity(123, 111)
    await old_turn(store, "学习智能体", 1)
    run = await accept_run(store, "回忆", 2)
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        await history(store, run, http).search("学习")
        await store.finish(run["id"], "completed", "done")
        assert not await worker(store, http).work_once(111)
        assert not await store.all("SELECT * FROM kestri.usage WHERE kind='history_index'")
        assert (
            await store.one(
                "SELECT status FROM kestri.history_index_jobs ORDER BY created_at LIMIT 1"
            )
        )["status"] == "succeeded"
    service = DataService(store, Workspace(tmp_path / "source"), settings())
    path = await service.backup(tmp_path / "backup.json")
    bundle = read_private(path)
    assert bundle["schema"] == 9 and bundle["tables"]["history_index_jobs"]
    assert "history_embeddings" not in bundle["tables"]
    await store.execute("TRUNCATE " + ",".join("kestri." + name for name in TABLES) + " CASCADE")
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        if (await store.one("SELECT to_regclass(%s) AS name", ("public." + table,)))["name"]:
            await store.execute("DELETE FROM public." + table)
    await DataService(store, Workspace(tmp_path / "restore"), settings()).restore(path, apply=True)
    assert all(
        j["status"] == "cancelled"
        for j in await store.all("SELECT * FROM kestri.history_index_jobs")
    )
    await store.execute("TRUNCATE " + ",".join("kestri." + name for name in TABLES) + " CASCADE")
    bundle["schema"] = 6
    del bundle["tables"]["image_inputs"]
    del bundle["image_bytes"]
    for row in bundle["tables"]["runs"]:
        del row["media_group_id"]
    for row in bundle["tables"]["conversations"]:
        del row["memory_choice"]
    for row in bundle["tables"]["outbox"]:
        del row["presentation"]
    del bundle["tables"]["history_index_jobs"]
    legacy = tmp_path / "legacy.json"
    write_private(
        legacy, encoded({"payload": bundle, "sha256": hashlib.sha256(encoded(bundle)).hexdigest()})
    )
    await DataService(store, Workspace(tmp_path / "legacy"), research_settings()).restore(
        legacy, apply=True
    )
    assert not await store.all("SELECT * FROM kestri.history_index_jobs")


async def test_source_change_in_flight_requeues_current_version(configured: Any) -> None:
    store = configured
    await old_turn(store, "学习智能体", 1)

    async def respond(request: httpx.Request) -> httpx.Response:
        await store.execute(
            "UPDATE kestri.messages SET content='改学英语' WHERE direction='in' AND telegram_id=1"
        )
        return response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        assert await worker(store, http).work_once(111)
    job = await store.one("SELECT * FROM kestri.history_index_jobs")
    assert job["status"] == "queued" and job["source_revision"] == 2 and job["run_id"] is None
    assert not await store.all("SELECT * FROM kestri.history_embeddings")
    assert (await store.one("SELECT state FROM kestri.usage WHERE kind='history_index'"))[
        "state"
    ] == "recorded"
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        assert await worker(store, http).work_once(111)
        assert (await store.one("SELECT status FROM kestri.history_index_jobs"))[
            "status"
        ] == "succeeded"
