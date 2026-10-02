"""Read actual injection/tool receipts, rechecking revocable sources at inspection."""

import re
from typing import Any


async def explain(conn: Any, chat_id: int, target: str | None = None) -> str:
    if target and not re.fullmatch(r"[0-9a-f-]{8,36}", target):
        return "回答编号不正确，请提供 /runs 中的编号。"
    runs = await (
        await conn.execute(
            """
        SELECT r.*, c.memory_epoch AS current_epoch, c.memory_use_enabled,
               c.auto_memory_enabled
        FROM kestri.runs AS r JOIN kestri.conversations AS c ON c.chat_id = r.chat_id
        WHERE r.chat_id = %s AND r.status = 'completed' AND r.kind = 'foreground'
          AND NOT r.history_expired AND (%s::text IS NULL OR r.id::text LIKE %s)
        ORDER BY r.created_at DESC LIMIT 2
    """,
            (chat_id, target, (target or "") + "%"),
        )
    ).fetchall()
    if not runs or (target and len(runs) != 1):
        return "没有找到唯一的已完成回答。可以提供 /runs 中的回答编号。"
    run = runs[0]
    records = await (
        await conn.execute(
            """
        SELECT kind, metadata FROM kestri.events
        WHERE run_id = %s AND kind IN ('memory_injected','history_diagnostic')
        ORDER BY sequence LIMIT 100
    """,
            (run["id"],),
        )
    ).fetchall()
    if not records:
        return "这次回答没有可用的记忆诊断记录。旧回答无法事后还原实际注入。"
    lines = [
        "这次回答的记忆依据",
        "",
        f"回答编号：{str(run['id'])[:8]}",
        "记录的是提供给模型的信息，不代表模型内部推理。",
        "",
    ]
    if run["memory_epoch"] != run["current_epoch"] or not run["memory_use_enabled"]:
        return "\n".join(lines + ["记忆状态已变更或使用已关闭，旧内容不再展示。"])
    injections = [r["metadata"] for r in records if r["kind"] == "memory_injected"]
    for number, injection in enumerate(injections, 1):
        lines.append(f"第 {number} 次模型调用")
        method = {"lexical": "关键词检索", "hybrid": "语义与关键词混合", "disabled": "记忆使用关闭"}
        lines.append("检索方式：" + method.get(injection["method"], "关键词检索"))
        if injection.get("fallback"):
            lines.append("语义检索未完成，本次使用关键词结果。")
        shown = 0
        for item in injection["memories"]:
            memory = await (
                await conn.execute(
                    """
                SELECT m.* FROM kestri.memories AS m
                LEFT JOIN kestri.tasks AS t ON t.id = m.task_id
                WHERE m.chat_id = %s AND m.id = %s AND m.revision = %s
                  AND m.status = 'active' AND m.origin != 'auto_inferred'
                  AND (m.expires_at IS NULL OR m.expires_at > now())
                  AND (m.review_after IS NULL OR m.review_after > now())
                  AND (m.valid_from IS NULL OR m.valid_from <= now())
                  AND (m.task_id IS NULL OR (m.task_id = %s AND t.status != 'deleted'))
                  AND (m.last_source_message_id IS NULL OR EXISTS (
                      SELECT 1 FROM kestri.messages WHERE id = m.last_source_message_id
                  ))
            """,
                    (chat_id, item["id"], item["revision"], run["task_id"]),
                )
            ).fetchone()
            if memory:
                label = "交流偏好" if item["category"] == "profile" else "相关记忆"
                lines.append(
                    f"• {label}：{memory['content'][:240]}\n  编号：{str(memory['id'])[:8]}"
                )
                if memory["last_source_message_id"]:
                    lines.append(f"  来源：/history {memory['last_source_message_id']}")
                shown += 1
        if not shown:
            lines.append("没有当前可展示的记忆；当时未注入，或记录已经失效。")
        lines.append("")
    history = [r["metadata"] for r in records if r["kind"] == "history_diagnostic"]
    if not history:
        lines.append("本次没有读取历史工具结果。")
    elif not run["auto_memory_enabled"]:
        lines.append("历史检索已关闭，旧片段不再展示。")
    else:
        for record in history:
            ids = record["archive_ids"]
            available = await (
                await conn.execute(
                    """
                SELECT id FROM kestri.messages WHERE chat_id = %s AND id = ANY(%s)
                ORDER BY id
            """,
                    (chat_id, ids),
                )
            ).fetchall()
            if len(available) == len(ids):
                label = "完整读取" if record["action"] == "read" else "搜索命中（不代表已读）"
                lines.append(label + "：" + "、".join(f"/history {r['id']}" for r in available))
            else:
                lines.append("历史片段已经清理，不再展示。")
    return "\n".join(lines)[:3200]
