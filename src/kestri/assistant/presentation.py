"""Shared control navigation; domain text stays separate from transport metadata."""

import re
from typing import Any

from kestri.memory.presentation import current_presentation

NAVIGATION = [
    [
        {"text": "任务", "callback_data": "ctl:tasks"},
        {"text": "记忆", "callback_data": "mem:list:0"},
    ],
    [
        {"text": "当前状态", "callback_data": "ctl:status"},
        {"text": "帮助", "callback_data": "ctl:help"},
    ],
]


def presentation(text: str, choice: dict[str, Any] | None = None) -> dict[str, Any]:
    buttons = list(NAVIGATION)
    if choice and choice.get("domain") == "task" and choice["mode"] == "select":
        buttons = [
            [
                {
                    "text": f"选择第 {index + 1} 个",
                    "callback_data": f"tc:{choice['token']}:{index + 1}",
                }
            ]
            for index, _ in enumerate(choice["targets"])
        ]
    else:
        next_page = re.search(r"下一页：/tasks ([0-9]{1,4})", text)
        if next_page:
            buttons.append([{"text": "下一页", "callback_data": f"tasks:list:{next_page[1]}"}])
        task_ids = re.findall(r"^[ \t]*编号：([a-f0-9]{8})", text, re.MULTILINE)
        if task_ids and text.startswith("你的持续任务"):
            buttons.extend(
                [{"text": f"查看第 {index + 1} 个", "callback_data": f"tasks:inspect:{identity}"}]
                for index, identity in enumerate(task_ids[:5])
            )
    return {"parse_mode": "HTML", "reply_markup": {"inline_keyboard": buttons}}


async def result_presentation(
    conn: Any, row: dict[str, Any], status: str, text: str, choice: dict[str, Any] | None
) -> dict[str, Any] | None:
    if row["kind"] == "memory_control":
        return await current_presentation(conn, row["chat_id"], text, choice)
    if row["kind"] == "task_control" or status != "completed":
        return presentation(text, choice)
    if row["kind"] == "foreground":
        return {
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": "记忆依据",
                            "callback_data": "mem:why:" + str(row["id"])[:8],
                        }
                    ]
                ]
            }
        }
    return None
