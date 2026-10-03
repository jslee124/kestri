"""Small Bot API adapter; no personal Telegram session or browser credentials."""

from typing import Any

import httpx

from kestri.errors import ProviderFailure
from kestri.integrations.http import post_json


class DeliveryProblem(Exception):
    def __init__(self, kind: str, *, uncertain: bool, delay: int = 3) -> None:
        self.kind = kind
        self.uncertain = uncertain
        self.delay = delay
        super().__init__(kind)


class TelegramClient:
    def __init__(self, token: str, client: httpx.AsyncClient) -> None:
        self._base = f"https://api.telegram.org/bot{token}"
        self.client = client

    async def call(self, method: str, payload: dict[str, Any]) -> Any:
        data = await post_json(
            self.client,
            f"{self._base}/{method}",
            payload,
            allow_error_json=True,
        )
        if data.get("ok") is False:
            parameters = data.get("parameters") or {}
            code = data.get("error_code")
            if not isinstance(code, int):
                raise ProviderFailure("InvalidTelegramResponse")
            if code == 429:
                raise DeliveryProblem(
                    "RateLimited",
                    uncertain=False,
                    delay=int(parameters.get("retry_after", 3)),
                )
            raise DeliveryProblem(f"TelegramRejected_{code}", uncertain=False)
        if data.get("ok") is not True:
            raise ProviderFailure("InvalidTelegramResponse")
        return data.get("result")

    async def identity(self) -> dict[str, Any]:
        result = await self.call("getMe", {})
        if not isinstance(result, dict) or not isinstance(result.get("id"), int):
            raise ProviderFailure("InvalidBotIdentity")
        return result

    async def configure_menu(self, owner_id: int) -> None:
        commands = [
            ("start", "Start and show capabilities", "开始使用与能力说明"),
            ("status", "View execution status", "查看执行状态"),
            ("runs", "View recent runs", "查看最近执行"),
            ("usage", "View estimated usage", "查看估算用量"),
            ("stop", "Stop the current run", "停止当前执行"),
            ("new", "Start fresh context; keep history", "新建对话上下文，保留历史"),
            ("help", "Show help", "查看使用帮助"),
            ("tasks", "List recurring tasks", "查看持续任务"),
            ("memory", "Inspect personal memory", "查看个人记忆"),
            ("remember", "Explicitly save memory", "显式保存记忆"),
            ("correct", "Correct a memory by ID", "按 ID 纠正记忆"),
            ("forget", "Forget a memory by ID", "按 ID 忘记记忆"),
            ("history", "Inspect original chat archive", "查看原始聊天记录"),
            ("task", "Manage a recurring task", "管理持续任务"),
        ]
        for language, description_index in (("", 1), ("zh", 2)):
            await self.call(
                "setMyCommands",
                {
                    "scope": {"type": "chat", "chat_id": owner_id},
                    "language_code": language,
                    "commands": [
                        {"command": item[0], "description": item[description_index]}
                        for item in commands
                    ],
                },
            )
        await self.call(
            "setChatMenuButton",
            {"chat_id": owner_id, "menu_button": {"type": "commands"}},
        )

    async def poll(self, offset: int | None = None, wait_seconds: int = 25) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": wait_seconds,
            "limit": 20,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = await self.call("getUpdates", payload)
        if not isinstance(result, list):
            raise ProviderFailure("InvalidUpdates")
        return result

    async def send(
        self,
        chat_id: int,
        text: str,
        reply_to: int | None = None,
        *,
        presentation: dict[str, Any] | None = None,
    ) -> int:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "link_preview_options": {"is_disabled": True},
            "reply_markup": {"remove_keyboard": True},
        }
        if presentation:
            if presentation.get("parse_mode") == "HTML":
                from kestri.memory.presentation import html_text

                payload["text"] = html_text(text)
            for key in ("parse_mode", "reply_markup"):
                if key in presentation:
                    payload[key] = presentation[key]
        if reply_to is not None:
            payload["reply_parameters"] = {
                "message_id": reply_to,
                "allow_sending_without_reply": True,
            }
        try:
            result = await self.call("sendMessage", payload)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as error:
            raise DeliveryProblem(type(error).__name__, uncertain=False) from error
        except (httpx.HTTPError, ProviderFailure) as error:
            raise DeliveryProblem(type(error).__name__, uncertain=True) from error
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
            raise DeliveryProblem("InvalidSendResponse", uncertain=True)
        return int(result["message_id"])


def authorized_message(update: dict[str, Any], owner_id: int) -> dict[str, Any] | None:
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    sender, chat = message.get("from", {}), message.get("chat", {})
    if (
        sender.get("id") != owner_id
        or sender.get("is_bot", False)
        or chat.get("type") != "private"
        or chat.get("id") != owner_id
        or not isinstance(message.get("text"), str)
        or not isinstance(message.get("message_id"), int)
    ):
        return None
    return message


def command_for(text: str) -> str | None:
    if text.strip().lower() in {"stop", "停止", "停下", "停止当前执行", "停止当前任务"}:
        return "stop"
    if text.startswith("/"):
        name = text.split(maxsplit=1)[0][1:].split("@", 1)[0].lower()
        return (
            name
            if name
            in {
                "start",
                "help",
                "stop",
                "status",
                "runs",
                "usage",
                "new",
                "tasks",
                "task",
                "memory",
                "remember",
                "correct",
                "forget",
                "history",
            }
            else "unknown"
        )
    return None


def authorized_callback(update: dict[str, Any], owner_id: int) -> dict[str, Any] | None:
    """Accept only our bounded management payloads from the owner in their private bot chat."""
    import re

    callback = update.get("callback_query")
    if not isinstance(callback, dict):
        return None
    message = callback.get("message") or {}
    sender = callback.get("from") or {}
    chat = message.get("chat") or {}
    data = callback.get("data")
    if (
        sender.get("id") != owner_id
        or sender.get("is_bot")
        or chat.get("id") != owner_id
        or chat.get("type") != "private"
        or not message.get("from", {}).get("is_bot")
        or not isinstance(data, str)
    ):
        return None
    command = None
    if re.fullmatch(r"ctl:(?:tasks|status|runs|usage|help)", data):
        command = "/" + data.split(":")[1]
    elif re.fullmatch(r"tasks:list:[0-9]{1,4}", data):
        command = "/tasks " + data.split(":")[2]
    elif re.fullmatch(r"tasks:inspect:[a-f0-9]{8}", data):
        command = "/tasks inspect " + data.split(":")[2]
    elif re.fullmatch(r"tc:[a-f0-9]{16}:[1-5]", data):
        _, token, choice = data.split(":")
        command = f"选择任务 {token} {choice}"
    elif re.fullmatch(r"mem:(?:changes|settings)", data):
        command = "/memory " + data.split(":")[1]
    elif re.fullmatch(r"mem:(?:list|pending):[0-9]{1,4}", data):
        _, action, page = data.split(":")
        command = f"/memory {action} {page}"
    elif re.fullmatch(r"mem:(?:why|inspect):[a-f0-9]{8}", data):
        _, action, target = data.split(":")
        command = f"/memory {action} {target}"
    elif re.fullmatch(r"mc:[a-f0-9]{16}:[1-5]", data):
        _, token, choice = data.split(":")
        command = f"选择记忆 {token} {choice}"
    if command is None or not isinstance(update.get("update_id"), int):
        return None
    return {"from": sender, "chat": chat, "message_id": -update["update_id"], "text": command}
