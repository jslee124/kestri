"""Concurrent polling, serialized foreground execution, and independent durable delivery."""

import asyncio
import logging
import signal
from typing import Any
from uuid import uuid4

import httpx
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.types.json import Jsonb

from kestri.budget import RunControl
from kestri.data import DataService
from kestri.errors import PolicyDenied, ProviderFailure
from kestri.memory import MemoryService, memory_instruction
from kestri.redaction import Redactor
from kestri.research import ResearchAgent
from kestri.runtime import build_model
from kestri.settings import ResearchSettings, TelegramCredentials
from kestri.store import Store
from kestri.task_intent import task_intent
from kestri.tasks import TaskService
from kestri.telegram import (
    DeliveryProblem,
    TelegramClient,
    authorized_message,
    command_for,
)
from kestri.url_policy import CloudflareResolver, PublicURLPolicy
from kestri.workspace import Workspace


class Application:
    def __init__(
        self,
        settings: ResearchSettings,
        store: Store,
        telegram: TelegramClient,
        researcher: ResearchAgent,
    ) -> None:
        self.settings = settings
        self.store = store
        self.telegram = telegram
        self.researcher = researcher
        self.active: tuple[RunControl, asyncio.Task[None]] | None = None
        self.background_active: tuple[RunControl, asyncio.Task[None]] | None = None
        self.tasks = TaskService(store, settings)
        self.wake_run = asyncio.Event()
        self.wake_delivery = asyncio.Event()

    async def accept_update(self, update: dict[str, Any]) -> bool:
        message = authorized_message(update, self.settings.telegram_owner_id)
        if message is None:
            return False
        reply = message.get("reply_to_message") or {}
        command = command_for(message["text"])
        intent = (
            task_intent(message["text"], task_reference=reply.get("message_id") is not None)
            if command in {None, "task"}
            else None
        )
        if message.get("forward_origin") or message.get("external_reply"):
            intent = None
        memory = memory_instruction(message["text"])
        if message.get("forward_origin") or message.get("external_reply"):
            memory = None
        if memory:
            kind = "memory_control"
        elif intent is not None:
            kind = "task_control"
        else:
            kind = "foreground"
        if memory:
            command = None
        if intent is not None:
            command = None
        accepted, run_id = await self.store.accept(
            update["update_id"],
            message["chat"]["id"],
            message["message_id"],
            message["text"],
            reply.get("message_id"),
            command,
            self.settings.queue_limit,
            kind,
            "forwarded"
            if message.get("forward_origin")
            else ("external_reply" if message.get("external_reply") else "direct"),
        )
        if accepted:
            if command == "stop":
                for active in (self.active, self.background_active):
                    if active and active[0].run_id == run_id:
                        active[0].cancel.set()
                        active[1].cancel()
            self.wake_run.set()
            self.wake_delivery.set()
        return accepted

    async def polling(self) -> None:
        while True:
            try:
                updates = await self.telegram.poll(await self.store.offset())
            except DeliveryProblem as error:
                if error.kind != "RateLimited":
                    raise
                await asyncio.sleep(max(1, min(error.delay, 120)))
                continue
            except httpx.HTTPError, ProviderFailure:
                await asyncio.sleep(3)
                continue
            for update in updates:
                if not isinstance(update.get("update_id"), int):
                    raise ProviderFailure("InvalidUpdateIdentity")
                await self.accept_update(update)
                # A poll confirms only offsets whose updates have already been handled durably.
                await self.store.advance_offset(update["update_id"])

    async def work_once(self, background: bool = False) -> bool:
        await MemoryService(self.store, self.settings).expire(self.settings.telegram_owner_id)
        row = await self.store.claim_run(background)
        if row is None:
            return False
        control = RunControl(self.store, row["id"])
        task = asyncio.create_task(self.researcher.run(row, control))
        if background:
            self.background_active = control, task
        else:
            self.active = control, task
        try:
            await task
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise asyncio.CancelledError
        except asyncio.CancelledError:
            await self.store.finish(
                row["id"],
                "cancelled",
                "执行已停止。",
                "Cancelled",
            )
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise
        except Exception as error:
            await self.store.finish(
                row["id"],
                "failed",
                "执行失败，未自动重跑。",
                type(error).__name__,
            )
        finally:
            if background:
                self.background_active = None
            else:
                self.active = None
            self.wake_delivery.set()
        return True

    async def working(self, background: bool = False) -> None:
        while True:
            self.wake_run.clear()
            if not await self.work_once(background):
                try:
                    await asyncio.wait_for(self.wake_run.wait(), timeout=1)
                except TimeoutError:
                    pass

    async def memory_maintaining(self) -> None:
        from kestri.embedding import EmbeddingClient
        from kestri.memory_index import MemoryIndexWorker
        from kestri.memory_worker import MemoryWorker

        worker = MemoryWorker(self.store, self.settings, self.researcher.model)
        config = self.settings.embedding_config()
        async with httpx.AsyncClient(
            timeout=self.settings.embedding_timeout_seconds, follow_redirects=False
        ) as http:
            indexer = (
                MemoryIndexWorker(self.store, self.settings, EmbeddingClient(config, http))
                if config
                else None
            )
            while True:
                try:
                    await worker.work_once(self.settings.telegram_owner_id)
                    if indexer:
                        await indexer.work_once(self.settings.telegram_owner_id)
                except Exception:
                    # Only a fixed category is logged; raw errors may contain private data.
                    logging.getLogger(__name__).warning("MemoryRepositoryUnavailable")
                    await asyncio.sleep(5)
                await asyncio.sleep(1)

    async def scheduling(self) -> None:
        while True:
            if await self.tasks.tick():
                self.wake_run.set()
            await asyncio.sleep(self.settings.scheduler_interval_seconds)

    async def deliver_once(self) -> bool:
        row = await self.store.claim_delivery()
        if row is None:
            return False
        try:
            identity = await self.telegram.send(row["chat_id"], row["content"], row["reply_to"])
        except DeliveryProblem as error:
            await self.store.delivery_failed(
                row,
                error.kind,
                uncertain=error.uncertain,
                delay=error.delay,
            )
        else:
            await self.store.delivered(row, identity)
        return True

    async def delivering(self) -> None:
        while True:
            self.wake_delivery.clear()
            if not await self.deliver_once():
                try:
                    await asyncio.wait_for(self.wake_delivery.wait(), timeout=1)
                except TimeoutError:
                    pass
            else:
                # Telegram private-chat rate limits apply across status and result messages.
                await asyncio.sleep(1.1)

    async def prepare_restore(self) -> None:
        marker = await self.store.one(
            "SELECT value FROM kestri.meta WHERE key='restore_quarantine'"
        )
        if not marker or not marker["value"].get("pending_updates"):
            return
        # A stale archive must not replay pending owner commands accepted after its snapshot.
        pending = await self.telegram.poll(offset=-1, wait_seconds=0)
        last = max((update["update_id"] for update in pending), default=None)
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                if last is not None:
                    await conn.execute(
                        "INSERT INTO kestri.meta(key,value) VALUES ('offset',%s) "
                        "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
                        (Jsonb(last + 1),),
                    )
                await conn.execute(
                    "UPDATE kestri.meta SET value=%s WHERE key='restore_quarantine'",
                    (Jsonb({"pending_updates": False}),),
                )
                await conn.execute(
                    "INSERT INTO kestri.outbox(id,chat_id,content) VALUES (%s,%s,%s)",
                    (
                        uuid4(),
                        self.settings.telegram_owner_id,
                        "备份恢复完成。导入记忆已隔离、持续任务已暂停、旧执行/发送未重放。"
                        "恢复启动前的 Telegram 待处理消息已跳过；请重新发送需要继续的请求。"
                        "用 /memory、/tasks 核对内容，再明确保存记忆或恢复任务。",
                    ),
                )

    async def serve(self) -> None:
        await self.prepare_restore()
        await self.store.recover()
        async with asyncio.TaskGroup() as group:
            group.create_task(self.polling())
            group.create_task(self.working())
            group.create_task(self.working(background=True))
            group.create_task(self.scheduling())
            group.create_task(self.delivering())
            group.create_task(self.memory_maintaining())
            group.create_task(
                DataService(self.store, self.researcher.workspace, self.settings).maintaining()
            )


async def run_telegram(settings: ResearchSettings) -> None:
    task = asyncio.current_task()
    if task is not None:
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)
    secrets = [
        secret.get_secret_value()
        for secret in (
            settings.deepseek_api_key,
            settings.telegram_bot_token,
            settings.tavily_api_key,
            settings.database_url,
        )
    ]
    if settings.dashscope_api_key is not None:
        secrets.append(settings.dashscope_api_key.get_secret_value())
    store = Store(settings.database_url.get_secret_value(), Redactor(secrets))
    model = build_model(settings)
    try:
        await store.open()
        async with (
            httpx.AsyncClient(timeout=40, follow_redirects=False) as telegram_http,
            httpx.AsyncClient(timeout=5, follow_redirects=False) as dns_http,
            httpx.AsyncClient(
                timeout=settings.request_timeout_seconds,
                follow_redirects=False,
                headers={"Authorization": f"Bearer {settings.tavily_api_key.get_secret_value()}"},
            ) as web_http,
            store.pool.connection() as lock_connection,
        ):
            telegram = TelegramClient(settings.telegram_bot_token.get_secret_value(), telegram_http)
            identity = await telegram.identity()
            webhook = await telegram.call("getWebhookInfo", {})
            if webhook.get("url"):
                raise PolicyDenied("ExistingWebhook")
            locked = await (
                await lock_connection.execute(
                    "SELECT pg_try_advisory_lock(hashtext(%s)) AS locked",
                    (f"kestri-bot-{identity['id']}",),
                )
            ).fetchone()
            if not locked or not locked["locked"]:
                raise PolicyDenied("BotAlreadyRunning")
            try:
                await store.bind_identity(identity["id"], settings.telegram_owner_id)
                saver = AsyncPostgresSaver(store.pool)
                await saver.setup()
                await telegram.configure_menu(settings.telegram_owner_id)
                researcher = ResearchAgent(
                    settings,
                    store,
                    Workspace(settings.workspace_dir),
                    saver,
                    model,
                    web_http,
                    PublicURLPolicy(CloudflareResolver(dns_http))
                    if settings.url_dns_mode == "cloudflare"
                    else PublicURLPolicy(),
                )
                print(
                    f"Kestri polling @{identity.get('username', '(unnamed)')}; "
                    "owner-only private chat."
                )
                await Application(
                    settings,
                    store,
                    telegram,
                    researcher,
                ).serve()
            finally:
                await lock_connection.execute("SELECT pg_advisory_unlock_all()")
    finally:
        await store.close()
        if model.root_async_client is not None:
            await model.root_async_client.close()
        if model.root_client is not None:
            model.root_client.close()


async def show_telegram_ids(settings: TelegramCredentials) -> None:
    async with httpx.AsyncClient(timeout=40, follow_redirects=False) as client:
        telegram = TelegramClient(settings.telegram_bot_token.get_secret_value(), client)
        identity = await telegram.identity()
        print(f"Open https://t.me/{identity.get('username', '')} and send /start yourself.")
        updates = await telegram.poll(wait_seconds=25)
        ids = {
            message["from"]["id"]
            for update in updates
            if isinstance((message := update.get("message")), dict)
            and message.get("chat", {}).get("type") == "private"
            and not message.get("from", {}).get("is_bot", True)
        }
        if not ids:
            print("No private user message found. Send /start, then run this command again.")
        for identity in sorted(ids):
            print(
                f"Observed private user ID: {identity}. "
                "Set KESTRI_TELEGRAM_OWNER_ID only to your own ID."
            )
        print("No owner was enrolled and no model work was started.")
