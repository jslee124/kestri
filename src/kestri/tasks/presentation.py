"""Human task summaries and bounded read-only detail views."""

import re
from typing import Any
from zoneinfo import ZoneInfo

from kestri.storage.store import Row

PAGE_SIZE = 5
STATUS = {"active": "已开启", "paused": "已暂停", "deleted": "已删除"}


def schedule(task: Row) -> str:
    days = task["weekdays"]
    cadence = (
        "每天" if len(days) == 7 else "每周" + "、".join("一二三四五六日"[day] for day in days)
    )
    return f"{cadence} {task['local_time']} · {task['timezone']}"


def agreement(task: Row) -> str:
    due = task["next_due"].astimezone(ZoneInfo(task["timezone"])).strftime("%m-%d %H:%M")
    lines = [
        "任务约定",
        "",
        task["title"],
        "状态：" + STATUS[task["status"]],
        "时间：" + schedule(task),
        "",
        "内容：" + task["instructions"],
        "",
        f"错过执行：{task['catch_up_seconds'] / 3600:g} 小时内合并补跑一次，超出则跳过。",
        ("下次计划：" + due) if task["status"] == "active" else "当前不会启动新的定时执行。",
        "编号：" + str(task["id"])[:8],
        "",
        "可以直接说：暂停这个简报，或回复这条消息修改时间。",
        "暂停/删除阻止后续启动；已经开始的执行需要单独停止。",
    ]
    if task.get("restored"):
        lines.append("此任务来自恢复备份，请核对后明确恢复。")
    return "\n".join(lines)


async def view(conn: Any, chat_id: int, text: str = "/tasks") -> str:
    args = text.split()[1:]
    if len(args) == 2 and args[0] == "inspect" and re.fullmatch(r"[a-f0-9-]{8,36}", args[1]):
        rows = await (
            await conn.execute(
                """
                SELECT * FROM kestri.tasks
                WHERE chat_id = %s AND status != 'deleted' AND id::text LIKE %s
                LIMIT 2
                """,
                (chat_id, args[1] + "%"),
            )
        ).fetchall()
        return agreement(rows[0]) if len(rows) == 1 else "没有找到唯一的当前任务。"
    if args and (len(args) != 1 or not re.fullmatch(r"[0-9]{1,4}", args[0])):
        return "页码或操作不正确，请发送 /tasks 查看任务。"
    page = int(args[0]) if args else 0
    rows = await (
        await conn.execute(
            """
            SELECT * FROM kestri.tasks
            WHERE chat_id = %s AND status != 'deleted'
            ORDER BY created_at, id
            LIMIT %s OFFSET %s
            """,
            (chat_id, PAGE_SIZE + 1, page * PAGE_SIZE),
        )
    ).fetchall()
    lines = ["你的持续任务", f"第 {page + 1} 页", ""]
    for task in rows[:PAGE_SIZE]:
        lines.extend(
            [
                f"• {task['title']} · {STATUS[task['status']]}",
                "  " + schedule(task),
                "  编号：" + str(task["id"])[:8],
                "",
            ]
        )
    if not rows:
        lines.append("暂无持续任务。可以说：每天早上八点给我 AI 新闻简报。")
    if len(rows) > PAGE_SIZE:
        lines.append(f"下一页：/tasks {page + 1}")
    return "\n".join(lines)
