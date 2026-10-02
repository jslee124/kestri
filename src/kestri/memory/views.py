"""Bounded owner views shared by slash commands and conversational controls."""

from typing import Any

from kestri.memory.presentation import PAGE_SIZE, detail, local_time


async def view(conn: Any, chat_id: int, args: list[str], timezone: str | None = None) -> str:
    state = await (
        await conn.execute("SELECT * FROM kestri.conversations WHERE chat_id = %s", (chat_id,))
    ).fetchone()
    assert state is not None
    settings = "\n".join(
        [
            "记忆设置",
            f"自动记忆：{'开启' if state['auto_memory_enabled'] else '关闭'}",
            f"回答时使用记忆：{'开启' if state['memory_use_enabled'] else '关闭'}",
            f"语义召回：{'开启' if state['memory_semantic_enabled'] else '关闭'}",
        ]
    )
    if args == ["settings"]:
        return settings + "\n\n可以直接告诉我：开启自动记忆，或暂时不要使用已有记忆。"
    if args and args[0] == "inspect":
        if len(args) != 2:
            return "请提供记忆编号，例如 /memory inspect 894c35f7。"
        import re

        if not re.fullmatch(r"[0-9a-f-]{8,36}", args[1]):
            return "记忆编号格式不正确。"
        rows = await (
            await conn.execute(
                """
                SELECT m.* FROM kestri.memories AS m
                LEFT JOIN kestri.tasks AS t ON t.id = m.task_id
                WHERE m.chat_id = %s AND m.id::text LIKE %s
                  AND m.status IN ('active', 'candidate', 'quarantined')
                  AND (m.expires_at IS NULL OR m.expires_at > now())
                  AND (m.review_after IS NULL OR m.review_after > now())
                  AND (m.valid_from IS NULL OR m.valid_from <= now())
                  AND (m.task_id IS NULL OR t.status != 'deleted')
                LIMIT 2
                """,
                (chat_id, args[1] + "%"),
            )
        ).fetchall()
        return (
            detail(rows[0], timezone)
            if len(rows) == 1
            else "没有找到唯一的当前记忆，请查看记忆列表。"
        )
    if args == ["changes"]:
        events = await (
            await conn.execute(
                """
            SELECT e.operation, e.created_at, m.content, m.id
            FROM kestri.memory_events AS e
            JOIN kestri.memories AS m ON m.id = e.memory_id
            WHERE e.chat_id = %s AND m.status = 'active'
              AND (m.expires_at IS NULL OR m.expires_at > now())
            ORDER BY e.id DESC LIMIT 10
        """,
                (chat_id,),
            )
        ).fetchall()
        pending = await (
            await conn.execute(
                """
            SELECT status, count(*) AS n FROM (
                SELECT status FROM kestri.memory_jobs WHERE chat_id = %s
                UNION ALL SELECT status FROM kestri.memory_index_jobs WHERE chat_id = %s
                UNION ALL SELECT status FROM kestri.history_index_jobs WHERE chat_id = %s
            ) AS work WHERE status IN ('queued','running','retry_wait','failed')
            GROUP BY status
        """,
                (chat_id, chat_id, chat_id),
            )
        ).fetchall()
        names = {"create": "新增", "replace": "更新", "reinforce": "确认", "candidate": "待确认"}
        lines = ["最近的记忆变化", ""]
        lines += [
            f"{local_time(r['created_at'], timezone)} · {names.get(r['operation'], '变更')}\n"
            f"{r['content'][:160]}"
            for r in events
        ]
        if not events:
            lines.append("最近没有有效记忆变化。")
        statuses = {
            "queued": "等待处理",
            "running": "处理中",
            "retry_wait": "等待重试",
            "failed": "失败",
        }
        lines += [
            "",
            "后台状态："
            + (
                "；".join(f"{statuses[r['status']]} {r['n']} 项" for r in pending)
                if pending
                else "已处理完成，暂无失败。"
            ),
        ]
        if any(r["status"] == "failed" for r in pending):
            lines.append(
                "部分维护任务失败；已有有效记忆仍可使用。请查看运行记录或联系维护者检查配置。"
            )
        return "\n".join(lines)
    page = 0
    mode = args[0] if args else "home"
    if mode not in {"home", "list", "pending"} or len(args) > 2:
        return "没有识别这个记忆操作。可以发送 /memory 查看首页，或直接描述你想做什么。"
    if len(args) == 2:
        if not args[1].isascii() or not args[1].isdigit() or len(args[1]) > 4:
            return "页码不正确，请从 /memory list 0 开始。"
        page = int(args[1])
    status = "candidate" if mode == "pending" else "active"
    counts = await (
        await conn.execute(
            """
        SELECT status, count(*) AS n FROM kestri.memories
        WHERE chat_id = %s AND status IN ('active','candidate')
          AND (expires_at IS NULL OR expires_at > now())
          AND (review_after IS NULL OR review_after > now())
          AND (valid_from IS NULL OR valid_from <= now())
          AND (task_id IS NULL OR EXISTS (
              SELECT 1 FROM kestri.tasks WHERE id = task_id AND status != 'deleted'
          )) GROUP BY status
    """,
            (chat_id,),
        )
    ).fetchall()
    total = {r["status"]: r["n"] for r in counts}
    rows = await (
        await conn.execute(
            """
        SELECT m.* FROM kestri.memories AS m LEFT JOIN kestri.tasks AS t ON t.id = m.task_id
        WHERE m.chat_id = %s AND m.status = %s
          AND (m.expires_at IS NULL OR m.expires_at > now())
          AND (m.review_after IS NULL OR m.review_after > now())
          AND (m.valid_from IS NULL OR m.valid_from <= now())
          AND (m.task_id IS NULL OR t.status != 'deleted')
        ORDER BY m.updated_at DESC, m.id LIMIT %s OFFSET %s
    """,
            (chat_id, status, PAGE_SIZE, page * PAGE_SIZE),
        )
    ).fetchall()
    if mode == "home":
        lines = [
            "你的记忆",
            "",
            *settings.splitlines()[1:],
            "",
            f"目前有 {total.get('active', 0)} 条有效记忆，{total.get('candidate', 0)} 条待确认。",
            "",
            "最近记住",
        ]
    else:
        lines = [
            "待确认的记忆" if status == "candidate" else "全部有效记忆",
            f"第 {page + 1} 页",
            "",
        ]
    lines += [f"• {r['content'][:180]}\n  编号：{str(r['id'])[:8]}" for r in rows]
    if not rows:
        lines.append(
            "暂无候选推断；候选不会进入回答。"
            if status == "candidate"
            else "暂无有效个人记忆。可以告诉我“记住……”来明确保存。"
        )
    if (page + 1) * PAGE_SIZE < total.get(status, 0):
        next_mode = "list" if status == "active" else "pending"
        lines += ["", f"下一页：/memory {next_mode} {page + 1}"]
    return "\n".join(lines)
