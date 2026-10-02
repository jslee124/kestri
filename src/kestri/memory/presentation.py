"""Human-facing memory text and safely escaped Telegram presentation."""

from datetime import datetime
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

PAGE_SIZE = 5
NAVIGATION = [
    [
        {"text": "查看全部", "callback_data": "mem:list:0"},
        {"text": "待确认", "callback_data": "mem:pending:0"},
    ],
    [
        {"text": "最近变化", "callback_data": "mem:changes"},
        {"text": "记忆设置", "callback_data": "mem:settings"},
    ],
]


def local_time(value: datetime | None, timezone: str | None = None) -> str:
    return (
        value.astimezone(ZoneInfo(timezone or "Asia/Shanghai")).strftime("%m-%d %H:%M")
        if value
        else "未记录"
    )


def detail(memory: dict[str, Any], timezone: str | None = None) -> str:
    origins = {
        "explicit_command": "你明确保存",
        "auto_direct": "自动记住",
        "auto_inferred": "待你确认",
    }
    state = {"active": "有效", "candidate": "待确认", "quarantined": "恢复后隔离"}.get(
        memory["status"], "当前不可用"
    )
    source = memory.get("last_source_message_id")
    return (
        f"记忆详情 · {state}\n\n{memory['content']}\n\n"
        f"范围：{'个人' if memory['task_id'] is None else '指定任务'}\n"
        f"记录方式：{origins.get(str(memory.get('origin')), '明确保存')}\n"
        f"更新：{local_time(memory['updated_at'], timezone)}\n"
        + (f"来源：/history {source}\n" if source else "")
        + (f"到期：{local_time(memory['expires_at'], timezone)}\n" if memory["expires_at"] else "")
        + f"编号：{str(memory['id'])[:8]}"
        + ("\n该记忆不参与回答，需要你重新明确保存。" if state == "恢复后隔离" else "")
    )


def presentation(text: str, choice: dict[str, Any] | None = None) -> dict[str, Any]:
    """Only application text is formatted. Escape every character before adding tags."""
    buttons = list(NAVIGATION)
    import re

    next_page = re.search(r"下一页：/memory (list|pending) ([0-9]+)", text)
    if next_page:
        buttons.append([{"text": "下一页", "callback_data": f"mem:{next_page[1]}:{next_page[2]}"}])
    ids = list(dict.fromkeys(re.findall(r"^[ \t]*编号：([a-f0-9]{8})", text, re.MULTILINE)))
    if len(ids) > 1:
        buttons += [
            [{"text": f"查看第 {i + 1} 条", "callback_data": f"mem:inspect:{identity}"}]
            for i, identity in enumerate(ids[:5])
        ]
    if choice:
        buttons = [
            [{"text": f"选择第 {i + 1} 条", "callback_data": f"mc:{choice['token']}:{i + 1}"}]
            for i, _ in enumerate(choice["targets"])
        ]
    return {"parse_mode": "HTML", "reply_markup": {"inline_keyboard": buttons}}


def html_text(text: str) -> str:
    lines = text.splitlines()
    return (
        "\n".join([f"<b>{escape(lines[0])}</b>", *[escape(line) for line in lines[1:]]])
        if lines
        else ""
    )


async def current_presentation(
    conn: Any,
    chat_id: int,
    text: str,
    choice: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = await (
        await conn.execute(
            "SELECT memory_epoch FROM kestri.conversations WHERE chat_id = %s", (chat_id,)
        )
    ).fetchone()
    result = presentation(text, choice)
    result["epoch"] = state["memory_epoch"]
    return result
