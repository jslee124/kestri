"""Shared offline transports and builders for research, task, and memory scenarios."""

import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from langchain_deepseek import ChatDeepSeek

from kestri.application import Application
from kestri.budget import RunControl
from kestri.memory import MemoryService
from kestri.models import DeepSeekChatModel
from kestri.settings import ResearchSettings
from kestri.store import Store
from kestri.tasks import TaskPlan, TaskService
from kestri.telegram import TelegramClient

from .conftest import test_settings

TEST_DSN = os.environ.get("KESTRI_TEST_DATABASE_URL")
NOW = datetime.now(UTC).replace(second=0, microsecond=0)
TIME = (NOW - timedelta(minutes=1)).strftime("%H:%M")
REQUEST = f"每天 {TIME} UTC 给我 AI 新闻简报"


async def resolve_public(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


async def resolve_private(host: str, port: int) -> list[str]:
    return ["127.0.0.1"]


def telegram_update(
    text: str = "Research this",
    user_id: int = 111,
    chat_type: str = "private",
    update_id: int = 1,
    message_id: int = 1,
    reply_to: int | None = None,
) -> dict:
    message = {
        "message_id": message_id,
        "text": text,
        "from": {"id": user_id, "is_bot": False},
        "chat": {"id": user_id, "type": chat_type},
    }
    if reply_to is not None:
        message["reply_to_message"] = {"message_id": reply_to}
    return {"update_id": update_id, "message": message}


def completion(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "offline-response",
        "object": "chat.completion",
        "created": 0,
        "model": "deepseek-flash",
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }


def tool_call(left: int, right: int, identity: str = "call-1") -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": identity,
                "type": "function",
                "function": {
                    "name": "checked_add",
                    "arguments": f'{{"left":{left},"right":{right}}}',
                },
            }
        ],
    }


def offline_model(
    responses: Sequence[dict[str, Any]], requests: list[dict[str, Any]]
) -> tuple[ChatDeepSeek, httpx.AsyncClient, httpx.Client]:
    remaining = iter(responses)

    def respond(request: httpx.Request) -> httpx.Response:
        import json

        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion(next(remaining)))

    transport = httpx.MockTransport(respond)
    async_client = httpx.AsyncClient(transport=transport)
    sync_client = httpx.Client(transport=transport)
    model = DeepSeekChatModel(
        model="deepseek-flash",
        api_key=test_settings().deepseek_api_key,
        api_base="https://api.deepseek.com/v1",
        http_async_client=async_client,
        http_client=sync_client,
        max_retries=0,
    )
    return model, async_client, sync_client


def research_settings(**overrides: Any) -> ResearchSettings:
    values = {
        "DEEPSEEK_API_KEY": "test-only-placeholder",
        "TELEGRAM_BOT_TOKEN": "123:abcdefghijklmnopqrstuvwxyz",
        "TAVILY_API_KEY": "test-tavily-placeholder",
        "DATABASE_URL": TEST_DSN or "postgresql://unused/kestri_test",
        "telegram_owner_id": 111,
        **overrides,
    }
    return ResearchSettings(_env_file=None, **values)


async def accept_run(store: Store, text: str = "Research", identity: int = 1) -> dict:
    accepted, _ = await store.accept(
        identity,
        111,
        identity,
        text,
        None,
        None,
        8,
    )
    assert accepted
    row = await store.claim_run()
    assert row is not None
    return row


def model_tool_call(name: str, args: dict, identity: str) -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": identity,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


class NeverResearch:
    async def run(self, row: dict, control: RunControl) -> None:
        raise AssertionError("research should not start")


def make_application(
    store: Store,
    client: httpx.AsyncClient,
    researcher: Any = None,
    options: ResearchSettings | None = None,
) -> Application:
    return Application(
        options or research_settings(),
        store,
        TelegramClient("123:placeholder", client),
        researcher or NeverResearch(),
    )


async def accept_task_control_run(
    store: Any, text: str, identity: int, reply: int | None = None
) -> dict:
    accepted, _ = await store.accept(
        identity,
        111,
        identity,
        text,
        reply,
        None,
        8,
        "task_control",
    )
    assert accepted
    row = await store.claim_run()
    assert row
    return row


async def create_task(store: Any, identity: int = 1) -> dict:
    row = await accept_task_control_run(store, REQUEST, identity)
    notice = await TaskService(store, research_settings()).apply(
        row,
        TaskPlan(
            action="create",
            title=f"AI {identity}",
            instructions="AI 新闻简报",
            local_time=TIME,
            timezone="UTC",
            weekdays=list(range(7)),
        ),
        "create",
        NOW - timedelta(days=1),
    )
    assert "UTC" in notice and "6 小时" in notice
    await store.finish(row["id"], "completed", notice)
    return await store.one("SELECT * FROM kestri.tasks WHERE authorized_run_id=%s", (row["id"],))


async def accept_memory_control_run(store: Any, text: str, identity: int) -> dict:
    accepted, _ = await store.accept(
        identity,
        111,
        identity,
        text,
        None,
        None,
        8,
        "memory_control",
    )
    assert accepted
    row = await store.claim_run()
    assert row
    return row


async def save_memory(store: Any, text: str = "回答使用中文", identity: int = 1) -> dict:
    row = await accept_memory_control_run(store, "/remember " + text, identity)
    notice = await MemoryService(store, research_settings()).apply(row)
    await store.finish(row["id"], "completed", notice)
    return await store.one("SELECT * FROM kestri.memories WHERE source_run_id=%s", (row["id"],))
