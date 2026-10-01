"""Small Bot API adapter; no personal Telegram session or browser credentials."""

from typing import Any

import httpx

from kestri.errors import ProviderFailure
from kestri.http import post_json


class DeliveryProblem(Exception):
    def __init__(self, kind: str, *, uncertain: bool, delay: int = 3) -> None:
        self.kind, self.uncertain, self.delay = kind, uncertain, delay
        super().__init__(kind)


class TelegramClient:
    def __init__(self, token: str, client: httpx.AsyncClient) -> None:
        self._base = f"https://api.telegram.org/bot{token}"
        self.client = client

    async def call(self, method: str, payload: dict[str, Any]) -> Any:
        data = await post_json(
            self.client, f"{self._base}/{method}", payload, allow_error_json=True
        )
        if data.get("ok") is False:
            parameters = data.get("parameters") or {}
            code = data.get("error_code")
            if not isinstance(code, int):
                raise ProviderFailure("InvalidTelegramResponse")
            if code == 429:
                raise DeliveryProblem(
                    "RateLimited", uncertain=False, delay=int(parameters.get("retry_after", 3))
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
            "setChatMenuButton", {"chat_id": owner_id, "menu_button": {"type": "commands"}}
        )

    async def poll(self, offset: int | None = None, wait_seconds: int = 25) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": wait_seconds,
            "limit": 20,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = await self.call("getUpdates", payload)
        if not isinstance(result, list):
            raise ProviderFailure("InvalidUpdates")
        return result

    async def send(self, chat_id: int, text: str, reply_to: int | None = None) -> int:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "link_preview_options": {"is_disabled": True},
            "reply_markup": {"remove_keyboard": True},
        }
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
            if name in {"start", "help", "stop", "status", "runs", "usage", "new", "tasks", "task"}
            else "unknown"
        )
    return None
