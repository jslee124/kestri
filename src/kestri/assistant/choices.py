"""Strict replies and short-lived owner choices; ordinary conversation is never a choice."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb


def selection(text: str) -> tuple[str | None, int] | None:
    callback = re.fullmatch(r"选择(?:任务|记忆) ([a-f0-9]{16}) ([1-5])", text.strip())
    if callback:
        return callback[1], int(callback[2]) - 1
    reply = re.fullmatch(
        r"(?:就)?(?:选|选择)?第?([一二三四五1-5])(?:条|个|项)(?:任务|记忆)?[。！!]?(?:就好)?",
        text.strip(),
    )
    if not reply:
        return None
    digit = reply[1]
    index = "一二三四五".index(digit) if digit in "一二三四五" else int(digit) - 1
    return None, index


def current(choice: dict[str, Any] | None, epoch: int, domain: str) -> bool:
    if not choice or choice.get("domain", "memory") != domain:
        return False
    try:
        expires = datetime.fromisoformat(choice["expires"])
        return expires > datetime.now(UTC) and choice["epoch"] == epoch
    except KeyError, TypeError, ValueError:
        return False


async def issue(conn: Any, chat_id: int, fields: dict[str, Any]) -> dict[str, Any]:
    state = await (
        await conn.execute(
            "SELECT memory_epoch FROM kestri.conversations WHERE chat_id = %s",
            (chat_id,),
        )
    ).fetchone()
    choice = {
        **fields,
        "token": uuid4().hex[:16],
        "epoch": state["memory_epoch"],
        "expires": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
    }
    await conn.execute(
        "UPDATE kestri.conversations SET memory_choice = %s WHERE chat_id = %s",
        (Jsonb(choice), chat_id),
    )
    return choice
