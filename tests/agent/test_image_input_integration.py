import base64
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from kestri.agent.budget import Budget, RunControl
from kestri.agent.context import ContextSummary
from kestri.agent.images import ImageInputs
from kestri.agent.research import ResearchAgent
from kestri.errors import PolicyDenied
from kestri.integrations.telegram import TelegramClient
from kestri.storage.lifecycle import DataService, encoded, read_private, write_private
from kestri.storage.store import Store
from kestri.storage.workspace import Workspace
from tests.agent.test_images import image_bytes, photo_update
from tests.helpers import (
    TEST_DSN,
    make_application,
    offline_model,
    research_settings,
    telegram_update,
)

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="Set a dedicated KESTRI_TEST_DATABASE_URL")


def image_transport(request: httpx.Request) -> httpx.Response:
    assert "authorization" not in request.headers
    if request.method == "POST":
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "file_path": "photos/" + json.loads(request.content)["file_id"] + ".png"
                },
            },
        )
    return httpx.Response(
        200, content=image_bytes("blue" if "photo-2" in request.url.path else "red")
    )


async def close_collection(store: Store) -> dict:
    await store.execute("UPDATE kestri.runs SET available_at=now() WHERE status='queued'")
    row = await store.claim_run()
    assert row
    return row


async def test_album_survives_restart_orders_members_and_acknowledges_once(store: Store) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(image_transport)) as client:
        app = make_application(store, client)
        assert await app.accept_update(photo_update(2, "second", "album"))
        assert not await app.accept_update(photo_update(2, "second", "album"))
        await store.advance_offset(2)
        await store.recover()
        app = make_application(store, client)
        assert await app.accept_update(photo_update(1, "first", "album"))
        assert await store.claim_run() is None
        assert len(await store.all("SELECT * FROM kestri.runs")) == 1
        assert len(await store.all("SELECT * FROM kestri.outbox")) == 1
        row = await close_collection(store)
        assert row["request"] == "first\nsecond"
        assert [
            r["message_id"]
            for r in await store.all(
                "SELECT message_id FROM kestri.image_inputs ORDER BY message_id"
            )
        ] == [1, 2]
        assert await app.accept_update(photo_update(3, "late", "album"))
        assert len(await store.all("SELECT * FROM kestri.runs")) == 1
        assert len(await store.all("SELECT * FROM kestri.image_inputs")) == 2
        notice = await store.one("SELECT content FROM kestri.outbox ORDER BY sequence DESC LIMIT 1")
        assert "重新发送" in notice["content"]


async def test_album_ceiling_and_image_count_reject_incomplete_analysis(store: Store) -> None:
    async with httpx.AsyncClient() as client:
        app = make_application(store, client)
        for identity in range(1, 12):
            assert await app.accept_update(photo_update(identity, group="album"))
        assert await store.claim_run() is None
        run = await store.one("SELECT status,error_type FROM kestri.runs")
        assert run == {"status": "failed", "error_type": "ImageCountLimit"}
        assert len(await store.all("SELECT * FROM kestri.image_inputs")) == 10


async def test_album_collection_cannot_extend_past_ten_seconds(store: Store) -> None:
    async with httpx.AsyncClient() as client:
        app = make_application(store, client)
        await app.accept_update(photo_update(1, group="album"))
        await store.execute("UPDATE kestri.runs SET created_at=now()-interval '9 seconds'")
        await app.accept_update(photo_update(2, group="album"))
    row = await store.one("SELECT available_at-created_at AS duration FROM kestri.runs")
    assert row["duration"] <= timedelta(seconds=10)


async def test_image_caption_cannot_control_tasks_or_become_automatic_memory(store: Store) -> None:
    async with httpx.AsyncClient() as client:
        app = make_application(store, client)
        await app.accept_update(telegram_update("hello"))
        await store.execute("UPDATE kestri.conversations SET auto_memory_enabled=true")
        await app.accept_update(photo_update(2, "/remember 我住在图片里"))
    assert (await store.one("SELECT kind FROM kestri.runs WHERE message_id=2"))[
        "kind"
    ] == "foreground"
    assert (await store.one("SELECT provenance FROM kestri.messages WHERE telegram_id=2"))[
        "provenance"
    ] == "image"
    assert not await store.all("SELECT * FROM kestri.memory_jobs")


async def test_text_followup_waits_for_the_album_ahead_of_it(store: Store) -> None:
    async with httpx.AsyncClient() as client:
        app = make_application(store, client)
        await app.accept_update(photo_update(1, group="album"))
        await app.accept_update(telegram_update("Explain image 1", update_id=2, message_id=2))
    assert await store.claim_run() is None
    row = await close_collection(store)
    assert row["media_group_id"] == "album"


async def test_postgres_checkpoints_store_references_and_summary_retains_them(
    store: Store, tmp_path: Path
) -> None:
    from langchain.agents import create_agent

    from kestri.agent.images import ImageContext

    requests = []
    model, async_client, sync_client = offline_model(
        [
            {"role": "assistant", "content": "A red image."},
            {"role": "assistant", "content": "The owner shared a red image."},
            {"role": "assistant", "content": "The image is still red."},
        ],
        requests,
    )
    workspace = Workspace(tmp_path / "workspace")
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(image_transport)) as client,
        AsyncPostgresSaver.from_conn_string(TEST_DSN) as saver,
    ):
        await saver.setup()
        agent = ResearchAgent(
            research_settings(),
            store,
            workspace,
            saver,
            model,
            client,
            telegram=TelegramClient("123:placeholder", client),
        )
        app = make_application(store, client, agent)
        await app.accept_update(photo_update())
        first = await store.claim_run()
        await agent.run(first, RunControl(store, first["id"]))
        snapshot = await saver.aget_tuple({"configurable": {"thread_id": first["id"]}})
        messages = snapshot.checkpoint["channel_values"]["messages"]
        assert "data:image" not in json.dumps([m.model_dump() for m in messages], default=str)
        await app.accept_update(telegram_update("second", update_id=2, message_id=2))
        second = await store.claim_run()
        summary = ContextSummary(
            model,
            Budget(
                research_settings(
                    input_token_budget=16000, context_trigger_ratio=0.1, context_keep_messages=4
                ),
                RunControl(store, second["id"]),
            ),
            [],
            "",
        )
        # Exercise the locked parent's real state-update hook, not just our summary helper.
        old_messages = [*messages, *[HumanMessage(content="x" * 100) for _ in range(6)]]
        state = await summary.abefore_model({"messages": old_messages}, None)
        assert state and state["messages"][1].additional_kwargs["image_refs"]
        image_agent = create_agent(model, middleware=[ImageContext(store, workspace, 111)])
        await image_agent.ainvoke({"messages": state["messages"][1:]})
    await async_client.aclose()
    sync_client.close()
    assert "data:image" not in json.dumps(requests[1])
    assert "data:image" in json.dumps(requests[2])


async def test_multiphoto_followup_reloads_pixels_without_persisting_base64(
    store: Store, tmp_path: Path
) -> None:
    requests: list[dict[str, Any]] = []
    model, async_client, sync_client = offline_model(
        [
            {"role": "assistant", "content": "The first image is red and the second is blue."},
            {"role": "assistant", "content": "The second image is blue."},
            {"role": "assistant", "content": "Two red images were compared."},
        ],
        requests,
    )
    saver = InMemorySaver()
    workspace = Workspace(tmp_path / "workspace")
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(image_transport)) as client,
        httpx.AsyncClient(
            headers={"Authorization": "Bearer test-tavily-placeholder"},
            transport=httpx.MockTransport(lambda request: httpx.Response(500)),
        ) as web_client,
    ):
        agent = ResearchAgent(
            research_settings(),
            store,
            workspace,
            saver,
            model,
            web_client,
            telegram=TelegramClient("123:placeholder", client),
        )
        app = make_application(store, client, agent)
        await app.accept_update(photo_update(2, "compare", "album"))
        await app.accept_update(photo_update(1, group="album"))
        row = await close_collection(store)
        await agent.run(row, RunControl(store, row["id"]))
        assert (await store.one("SELECT status FROM kestri.runs WHERE id=%s", (row["id"],)))[
            "status"
        ] == "completed"
        await app.accept_update(telegram_update("What about image 2?", update_id=3, message_id=3))
        followup = await store.claim_run()
        assert followup and followup["source_thread"] == row["id"]
        await agent.run(followup, RunControl(store, followup["id"]))
        snapshot = await saver.aget_tuple({"configurable": {"thread_id": followup["id"]}})
        assert snapshot
        messages = snapshot.checkpoint["channel_values"]["messages"]
        dumped = json.dumps([message.model_dump() for message in messages], default=str)
        assert "image_refs" in dumped and "data:image" not in dumped
        await app.accept_update(telegram_update("summarize", update_id=4, message_id=4))
        summary_run = await store.claim_run()
        assert summary_run
        summary = ContextSummary(
            model, Budget(research_settings(), RunControl(store, summary_run["id"])), [], ""
        )
        text = await summary._acreate_summary(messages)
        summarized = summary._build_new_messages(text)
        assert len(summarized[0].additional_kwargs["image_refs"]) == 2
    await async_client.aclose()
    sync_client.close()
    for request in requests[:2]:
        blocks = [
            block
            for message in request["messages"]
            if isinstance(message["content"], list)
            for block in message["content"]
            if block["type"] == "image_url"
        ]
        assert len(blocks) == 2
        assert [base64.b64decode(block["image_url"]["url"].split(",")[1]) for block in blocks] == [
            image_bytes(),
            image_bytes("blue"),
        ]
        assert "photo-" not in json.dumps(
            request
        ) and "abcdefghijklmnopqrstuvwxyz" not in json.dumps(request)
    assert "data:image" not in json.dumps(requests[2])


async def test_failed_download_never_calls_model(store: Store, tmp_path: Path) -> None:
    requests = []
    model, async_client, sync_client = offline_model([], requests)
    workspace = Workspace(tmp_path / "workspace")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    ) as client:
        agent = ResearchAgent(
            research_settings(),
            store,
            workspace,
            InMemorySaver(),
            model,
            client,
            telegram=TelegramClient("123:placeholder", client),
        )
        await make_application(store, client, agent).accept_update(photo_update())
        row = await store.claim_run()
        await agent.run(row, RunControl(store, row["id"]))
    assert not requests
    run = await store.one("SELECT status,result FROM kestri.runs")
    assert run["status"] == "failed" and "重新发送" in run["result"]
    await async_client.aclose()
    sync_client.close()


async def test_image_backup_export_restore_and_retention_cover_pixels(
    store: Store, tmp_path: Path
) -> None:
    await store.bind_identity(123, 111)
    workspace = Workspace(tmp_path / "source")
    async with httpx.AsyncClient(transport=httpx.MockTransport(image_transport)) as client:
        await make_application(store, client).accept_update(photo_update())
        row = await store.claim_run()
        refs = await ImageInputs(store, workspace, TelegramClient("123:secret", client)).prepare(
            row
        )
    await store.finish(row["id"], "completed", "red")
    service = DataService(store, workspace, research_settings())
    backup = await service.backup(tmp_path / "backup.json")
    exported = read_private(await service.backup(tmp_path / "export.json", export=True))
    assert exported["image_bytes"] == read_private(backup)["image_bytes"]
    # Validate corruption before applying any restore mutation.
    corrupted = read_private(backup)
    key = next(iter(corrupted["image_bytes"]))
    corrupted["image_bytes"][key] = base64.b64encode(image_bytes("blue")).decode("ascii")
    bad = tmp_path / "bad.json"
    write_private(
        bad,
        encoded({"payload": corrupted, "sha256": hashlib.sha256(encoded(corrupted)).hexdigest()}),
    )
    with pytest.raises(PolicyDenied, match="BackupImageMismatch"):
        await service.restore(bad)
    await store.execute("DROP SCHEMA kestri CASCADE")
    await store.open()
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        exists = await store.one("SELECT to_regclass(%s) AS name", (f"public.{table}",))
        if exists["name"]:
            await store.execute(f"DELETE FROM public.{table}")
    target = DataService(store, Workspace(tmp_path / "target"), research_settings())
    report = await target.restore(backup, apply=True)
    assert report["image_files"] == 1
    assert target.workspace.read_image(row["id"], refs[0], 10000) == image_bytes()
    assert (await store.one("SELECT file_id FROM kestri.image_inputs"))["file_id"] == ""
    report = await target.cleanup(apply=True, erase=True)
    assert report["images"] == 1 and not report["deferred"]
    assert not (target.workspace.root / row["id"] / f"{refs[0]}.image").exists()
    assert (await store.one("SELECT status,caption,cleanup_pending FROM kestri.image_inputs")) == {
        "status": "expired",
        "caption": "",
        "cleanup_pending": False,
    }


async def test_existing_private_image_is_adopted_after_interrupted_write(
    store: Store, tmp_path: Path
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: pytest.fail("must reuse completed local write")
        )
    ) as client:
        await make_application(store, client).accept_update(photo_update())
        row = await store.claim_run()
        record = await store.one("SELECT id FROM kestri.image_inputs")
        workspace = Workspace(tmp_path / "workspace")
        workspace.write_image(row["id"], str(record["id"]), image_bytes())
        refs = await ImageInputs(store, workspace, TelegramClient("123:secret", client)).prepare(
            row
        )
        assert refs == [str(record["id"])]
        assert (await store.one("SELECT status FROM kestri.image_inputs"))["status"] == "ready"


async def test_tampered_expired_and_other_owner_images_never_reach_model(
    store: Store, tmp_path: Path
) -> None:
    from langchain.agents import create_agent

    from kestri.agent.images import ImageContext, ImageInputFailure

    requests = []
    model, async_client, sync_client = offline_model([], requests)
    workspace = Workspace(tmp_path / "workspace")
    async with httpx.AsyncClient(transport=httpx.MockTransport(image_transport)) as client:
        await make_application(store, client).accept_update(photo_update())
        run = await store.claim_run()
        refs = await ImageInputs(store, workspace, TelegramClient("123:secret", client)).prepare(
            run
        )
    messages = [HumanMessage(content="inspect", additional_kwargs={"image_refs": refs})]
    image_agent = create_agent(model, middleware=[ImageContext(store, workspace, 222)])
    with pytest.raises(ImageInputFailure):
        await image_agent.ainvoke({"messages": messages})
    image_agent = create_agent(model, middleware=[ImageContext(store, workspace, 111)])
    await store.execute("UPDATE kestri.image_inputs SET status='expired'")
    with pytest.raises(ImageInputFailure):
        await image_agent.ainvoke({"messages": messages})
    await store.execute("UPDATE kestri.image_inputs SET status='ready'")
    path = workspace.root / run["id"] / f"{refs[0]}.image"
    path.write_bytes(image_bytes("blue"))
    with pytest.raises(ImageInputFailure):
        await image_agent.ainvoke({"messages": messages})
    assert not requests
    await async_client.aclose()
    sync_client.close()


async def test_total_image_bytes_fail_before_any_model_call(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kestri.agent import images

    requests = []
    model, async_client, sync_client = offline_model([], requests)
    monkeypatch.setattr(images, "MAX_TOTAL_BYTES", len(image_bytes()))
    async with httpx.AsyncClient(transport=httpx.MockTransport(image_transport)) as client:
        workspace = Workspace(tmp_path / "workspace")
        agent = ResearchAgent(
            research_settings(),
            store,
            workspace,
            InMemorySaver(),
            model,
            client,
            telegram=TelegramClient("123:placeholder", client),
        )
        app = make_application(store, client, agent)
        await app.accept_update(photo_update(1, group="album"))
        await app.accept_update(photo_update(2, group="album"))
        run = await close_collection(store)
        await agent.run(run, RunControl(store, run["id"]))
    result = await store.one("SELECT status,result FROM kestri.runs")
    assert result["status"] == "failed" and "20 MiB" in result["result"]
    assert not requests
    await async_client.aclose()
    sync_client.close()


async def test_restore_expires_pending_images_without_redownloading(
    store: Store, tmp_path: Path
) -> None:
    await store.bind_identity(123, 111)
    async with httpx.AsyncClient() as client:
        await make_application(store, client).accept_update(photo_update(caption="private caption"))
    source = DataService(store, Workspace(tmp_path / "source"), research_settings())
    backup = await source.backup(tmp_path / "backup.json")
    await store.execute("DROP SCHEMA kestri CASCADE")
    await store.open()
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        exists = await store.one("SELECT to_regclass(%s) AS name", (f"public.{table}",))
        if exists["name"]:
            await store.execute(f"DELETE FROM public.{table}")
    target = DataService(store, Workspace(tmp_path / "target"), research_settings())
    await target.restore(backup, apply=True)
    assert (await store.one("SELECT status,file_id,caption FROM kestri.image_inputs")) == {
        "status": "expired",
        "file_id": "",
        "caption": "",
    }
    assert await store.claim_run() is None


async def test_cleanup_retries_unlink_after_database_expiration(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = Workspace(tmp_path / "workspace")
    async with httpx.AsyncClient(transport=httpx.MockTransport(image_transport)) as client:
        await make_application(store, client).accept_update(photo_update())
        run = await store.claim_run()
        refs = await ImageInputs(store, workspace, TelegramClient("123:secret", client)).prepare(
            run
        )
    await store.finish(run["id"], "completed", "red")
    await store.execute("UPDATE kestri.outbox SET status='sent'")
    service = DataService(store, workspace, research_settings())
    remove = workspace.remove_image

    def fail_unlink(*args) -> None:
        raise OSError("simulated disk failure")

    monkeypatch.setattr(workspace, "remove_image", fail_unlink)
    with pytest.raises(OSError):
        await service.cleanup(apply=True, erase=True)
    assert (await store.one("SELECT status,cleanup_pending FROM kestri.image_inputs")) == {
        "status": "expired",
        "cleanup_pending": True,
    }
    monkeypatch.setattr(workspace, "remove_image", remove)
    await service.cleanup(apply=True, erase=True)
    assert not (workspace.root / run["id"] / f"{refs[0]}.image").exists()
    assert not (await store.one("SELECT cleanup_pending FROM kestri.image_inputs"))[
        "cleanup_pending"
    ]
