"""Read-only operational views, shared by commands and natural queries."""

import re
from typing import Any

from kestri.memory.presentation import local_time

STATUSES = {
    "queued": "等待处理",
    "running": "执行中",
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已停止",
    "interrupted": "已中断",
}
KINDS = {
    "foreground": "对话",
    "background": "定时简报",
    "task_control": "任务管理",
    "memory_control": "记忆管理",
    "memory_maintenance": "记忆维护",
}


async def view(conn: Any, command: str, chat_id: int, text: str, timezone: str | None) -> str:
    if command in {"start", "help"}:
        return (
            "Kestri 使用帮助\n\n"
            "直接提问、查询公开网页，或回复之前的结果继续讨论。\n\n"
            "日常控制\n"
            "• 我有哪些任务？\n• 现在在做什么？\n• 停止当前执行\n• 开始新话题\n\n"
            "个人记忆\n"
            "• 你记住了我哪些事情？\n• 开启自动记忆和语义检索\n"
            "• 回答时不要使用我的记忆\n• 为什么刚才这样回答？\n\n"
            "持续任务\n"
            "• 每天早上八点给我 AI 新闻简报\n• 暂停新闻简报\n"
            "回复任务结果可修改；目标有歧义时选择对应项。\n\n"
            "仍可使用 /tasks、/memory、/status、/runs、/usage 和 /stop。\n"
            "聊天通过 Telegram；模型处理使用 DeepSeek，网页研究使用 Tavily。"
        )
    if command == "usage":
        row = await (
            await conn.execute(
                """
                SELECT COALESCE(sum(amount_micro_usd), 0) AS amount, count(*) AS calls
                FROM kestri.usage
                WHERE created_at >= date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
                """,
            )
        ).fetchone()
        return (
            "本月用量（UTC）\n\n"
            f"本地估算/预留：${int(row['amount']) / 1_000_000:.4f}\n"
            f"计费操作：{row['calls']} 次\n\n"
            "这不是提供方账单；结果未知的请求仍保留预留额度。"
        )
    args = text.split()[1:] if text.startswith("/") else []
    target = None
    if args:
        if len(args) != 2 or args[0] != "inspect" or not re.fullmatch(r"[a-f0-9-]{8,36}", args[1]):
            return "请发送 /runs，或 /runs inspect 执行编号。"
        target = args[1]
    active_only = command == "status"
    rows = await (
        await conn.execute(
            """
            SELECT r.*,
                   (SELECT count(*) FROM kestri.evidence AS e WHERE e.run_id = r.id) AS evidence,
                   (SELECT count(*) FROM kestri.usage AS u WHERE u.run_id = r.id) AS calls,
                   (SELECT count(*) FROM kestri.outbox AS o
                    WHERE o.run_id = r.id
                      AND o.status IN ('uncertain', 'failed')) AS delivery_problems
            FROM kestri.runs AS r
            WHERE r.chat_id = %s
              AND (%s::text IS NULL OR r.id::text LIKE %s)
              AND (NOT %s OR r.status IN ('queued', 'running'))
            ORDER BY r.created_at DESC
            LIMIT 5
            """,
            (chat_id, target, (target or "") + "%", active_only),
        )
    ).fetchall()
    if target and len(rows) != 1:
        return "没有找到唯一的执行，请查看最近执行列表。"
    lines = ["当前状态" if active_only else "最近执行", ""]
    for row in rows:
        lines.append(f"• {KINDS.get(row['kind'], '执行')} · {STATUSES[row['status']]}")
        if not row["history_expired"]:
            lines.append(row["request"][:96].replace("\n", " "))
        lines.append(f"时间：{local_time(row['created_at'], timezone)}")
        lines.append(f"来源 {row['evidence']} · 计费操作 {row['calls']}")
        if row["delivery_problems"]:
            lines.append("有发送结果待核对，不能确认已经收到。")
        if row["error_type"]:
            lines.append("错误类别：" + row["error_type"])
        lines.extend(["执行编号：" + str(row["id"])[:8], ""])
    if not rows:
        lines.append("当前没有进行中或排队的执行。" if active_only else "暂无执行记录。")
    lines.append("停止当前执行可直接告诉我；暂停定时任务需要明确任务目标。")
    return "\n".join(lines)
