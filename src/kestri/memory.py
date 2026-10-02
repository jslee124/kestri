"""Explicit owner memory commands; no model, inference, or archive extraction writes."""

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from kestri.errors import PolicyDenied
from kestri.settings import ResearchSettings
from kestri.store import Row, Store


def memory_instruction(text: str) -> tuple[str, str] | None:
    match = re.match(r"^/(remember|correct|forget)(?:@[\w]+)?(?:\s+(.*))?$", text.strip(), re.S)
    if match:
        return match[1], (match[2] or "").strip()
    for prefix, action in (
        ("记住", "remember"),
        ("更正记忆", "correct"),
        ("忘记记忆", "forget"),
    ):
        if text.strip().startswith(prefix):
            return action, text.strip()[len(prefix) :].lstrip(" ：:")
    return None


def display(memory: Row) -> str:
    scope = "global" if memory["task_id"] is None else "task " + str(memory["task_id"])[:8]
    return (
        f"记忆 {str(memory['id'])[:8]} · {scope} · {memory['status']}\n"
        f"内容：{memory['content']}\n来源消息：{memory['source_message_id']}\n"
        f"创建：{memory['created_at'].isoformat()}；更新：{memory['updated_at'].isoformat()}\n"
        f"到期：{memory['expires_at'].isoformat() if memory['expires_at'] else '无'}"
        + (
            "\n恢复隔离，不参与上下文；重新启用请用完整 /remember 指令保存。"
            if memory["status"] == "quarantined"
            else ""
        )
    )


async def listing(conn: Any, chat_id: int) -> str:
    rows = await (
        await conn.execute(
            (
                "SELECT * FROM kestri.memories WHERE chat_id=%s "
                "AND status IN ('active','quarantined') AND (expires_at IS NULL OR "
                "expires_at>now()) ORDER BY (status='active') DESC,updated_at DESC LIMIT 64"
            ),
            (chat_id,),
        )
    ).fetchall()
    return (
        "\n\n".join(display(row) for row in rows)
        or "暂无有效个人记忆。用 /remember 内容 显式保存。"
    )


class MemoryService:
    def __init__(self, store: Store, settings: ResearchSettings) -> None:
        self.store = store
        self.settings = settings

    async def apply(self, run: Row) -> str:
        instruction = memory_instruction(run["request"])
        if run["kind"] != "memory_control" or instruction is None:
            raise PolicyDenied("MemoryAuthorizationUnavailable")
        action, body = instruction
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    ("SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE"),
                    (run["chat_id"],),
                )
                current = await (
                    await conn.execute(
                        ("SELECT * FROM kestri.runs WHERE id=%s FOR UPDATE"),
                        (run["id"],),
                    )
                ).fetchone()
                if (
                    not current
                    or current["status"] != "running"
                    or current["cancel_requested"]
                    or current["kind"] != "memory_control"
                    or current["request"] != run["request"]
                ):
                    raise PolicyDenied("RunInactive")
                prior = await (
                    await conn.execute(
                        ("SELECT result FROM kestri.memory_changes WHERE run_id=%s"),
                        (run["id"],),
                    )
                ).fetchone()
                if prior:
                    return str(prior["result"])
                changed = False
                notice = "未作变更。使用 /remember 内容；/correct 记忆ID 新内容；/forget 记忆ID。"
                if not body or len(body) > 1200:
                    notice = "未作变更。请提供 1–1200 字符的内容或明确记忆 ID。"
                elif action == "remember":
                    task_id = None
                    expires = None
                    if body.startswith("expires="):
                        expiry_parts = body.split(maxsplit=1)
                        try:
                            expires = datetime.fromisoformat(expiry_parts[0][8:])
                            if (
                                expires.tzinfo is None
                                or expires <= datetime.now(UTC)
                                or len(expiry_parts) != 2
                            ):
                                raise ValueError("InvalidExpiry")
                        except ValueError:
                            return "未保存。expires= 需要带时区的未来 ISO 时间及记忆内容。"
                        body = expiry_parts[1]

                    scoped = re.match(r"^task ([0-9a-f-]{8,36}) (.+)$", body, re.S)
                    if scoped:
                        targets = await (
                            await conn.execute(
                                (
                                    "SELECT id FROM kestri.tasks WHERE chat_id=%s AND "
                                    "status!='deleted' AND id::text LIKE %s"
                                ),
                                (run["chat_id"], scoped[1] + "%"),
                            )
                        ).fetchall()
                        if len(targets) != 1:
                            return "未保存。任务目标不明确，请提供 /tasks 中的 ID。"
                        task_id, body = targets[0]["id"], scoped[2]
                    elif body.startswith("task "):
                        return "未保存。任务范围格式：/remember task 任务ID 内容。"
                    notice, changed = await self._insert(
                        conn,
                        run,
                        body,
                        task_id,
                        expires=expires,
                    )
                else:
                    parts = body.split(maxsplit=1)
                    if re.fullmatch(r"[0-9a-f-]{8,36}", parts[0]):
                        targets = await (
                            await conn.execute(
                                (
                                    "SELECT * FROM kestri.memories WHERE chat_id=%s "
                                    "AND status='active' AND id::text LIKE %s FOR "
                                    "UPDATE"
                                ),
                                (run["chat_id"], parts[0] + "%"),
                            )
                        ).fetchall()
                        if len(targets) == 1 and (
                            action == "forget"
                            and len(parts) == 1
                            or action == "correct"
                            and len(parts) == 2
                        ):
                            old = targets[0]
                            if action == "correct":
                                notice, changed = await self._insert(
                                    conn,
                                    run,
                                    parts[1],
                                    old["task_id"],
                                    old["id"],
                                    old["expires_at"],
                                )
                            else:
                                notice, changed = (
                                    f"已忘记记忆 {str(old['id'])[:8]}；"
                                    "已移出有效检索和对话上下文。历史仍保留。",
                                    True,
                                )
                            if changed:
                                await conn.execute(
                                    (
                                        "UPDATE kestri.memories SET status=%s,"
                                        "updated_at=now() WHERE id=%s"
                                    ),
                                    (
                                        "forgotten" if action == "forget" else "superseded",
                                        old["id"],
                                    ),
                                )
                        else:
                            notice = "未作变更。目标不明确或格式不完整，请用 /memory 查看 ID。"
                if changed:
                    await conn.execute(
                        (
                            "UPDATE kestri.conversations SET thread_id=NULL,"
                            "memory_epoch=memory_epoch+1,updated_at=now() "
                            "WHERE chat_id=%s"
                        ),
                        (run["chat_id"],),
                    )
                await conn.execute(
                    ("INSERT INTO kestri.memory_changes(run_id,result) VALUES (%s,%s)"),
                    (run["id"], self.store.redactor.text(notice)),
                )
                return notice

    async def _insert(
        self,
        conn: Any,
        run: Row,
        content: str,
        task_id: Any,
        supersedes: Any = None,
        expires: datetime | None = None,
    ) -> tuple[str, bool]:
        if re.search(
            (
                "\\[REDACTED\\]|\\b(?:sk-|tvly-|[0-9]{6,}:)[A-Za-z0-9_"
                "-]{12,}|password\\s*[:=]|密码\\s*[:：=]|API[_ "
                "]?KEY\\s*[:=]|PRIVATE KEY"
            ),
            content,
            re.I,
        ):
            return "未保存。凭据应保存在本地秘密配置，不能进入个人记忆。", False
        count = await (
            await conn.execute(
                ("SELECT count(*) AS n FROM kestri.memories WHERE chat_id=%s AND status='active'"),
                (run["chat_id"],),
            )
        ).fetchone()
        if count and count["n"] >= self.settings.memory_limit and supersedes is None:
            return "未保存。有效记忆数量已达上限，请先纠正或忘记旧项。", False
        row = await (
            await conn.execute(
                (
                    "INSERT INTO kestri.memories(id,chat_id,content,"
                    "scope,task_id,source_message_id,source_run_id,"
                    "status,supersedes,expires_at) VALUES (%s,%s,%s,%s,"
                    "%s,%s,%s,'active',%s,%s) RETURNING *"
                ),
                (
                    uuid4(),
                    run["chat_id"],
                    content,
                    "global" if task_id is None else "task",
                    task_id,
                    run["message_id"],
                    run["id"],
                    supersedes,
                    expires,
                ),
            )
        ).fetchone()
        return "已保存：\n" + display(row) + "\n旧活跃对话已重置；原始历史保留。", True

    async def expire(self, chat_id: int) -> None:
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    ("SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE"),
                    (chat_id,),
                )
                rows = await (
                    await conn.execute(
                        (
                            "UPDATE kestri.memories SET status='expired',"
                            "updated_at=now() WHERE chat_id=%s AND "
                            "status='active' AND expires_at<=now() RETURNING id"
                        ),
                        (chat_id,),
                    )
                ).fetchall()
                if rows:
                    await conn.execute(
                        (
                            "UPDATE kestri.conversations SET thread_id=NULL,"
                            "memory_epoch=memory_epoch+1 WHERE chat_id=%s"
                        ),
                        (chat_id,),
                    )

    async def retrieve(self, run: Row) -> list[Row]:
        # Always apply task scope; no automatic extraction from source messages or old summaries.
        rows = await self.store.all(
            (
                "SELECT m.* FROM kestri.memories m LEFT JOIN "
                "kestri.tasks t ON t.id=m.task_id WHERE "
                "m.chat_id=%s AND m.status='active' AND "
                "(m.expires_at IS NULL OR m.expires_at>now()) AND "
                "(m.task_id IS NULL OR (m.task_id=%s AND "
                "t.status!='deleted')) ORDER BY m.updated_at DESC "
                "LIMIT 64"
            ),
            (run["chat_id"], run.get("task_id")),
        )
        terms = set(re.findall(r"[a-zA-Z0-9_]{2,}|[\u4e00-\u9fff]{2}", run["request"].lower()))
        rows.sort(
            key=lambda r: (
                r["task_id"] is not None,
                sum(term in r["content"].lower() for term in terms),
            ),
            reverse=True,
        )
        return rows[: self.settings.memory_context_limit]
