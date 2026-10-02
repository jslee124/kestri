"""Explicit owner memory commands; no model, inference, or archive extraction writes."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from kestri.errors import PolicyDenied
from kestri.memory.intent import NaturalMemoryControl, natural_control, normalize_target
from kestri.memory.retriever import lexical_rank
from kestri.settings import ResearchSettings
from kestri.storage.store import Row, Store


def memory_instruction(text: str) -> tuple[str, str] | None:
    if re.fullmatch(
        r"(?:选择记忆 [a-f0-9]{16} [1-5]|(?:就)?(?:选|选择)?第?[一二三四五1-5]条"
        r"(?:记忆)?)[。！!]?(?:就好)?",
        text.strip(),
    ):
        return "choose", text.strip()
    match = re.match(r"^/(remember|correct|forget)(?:@[\w]+)?(?:\s+(.*))?$", text.strip(), re.S)
    if match:
        return match[1], (match[2] or "").strip()
    natural = natural_control(text)
    if natural:
        return natural.action, text.strip()
    for prefix, action in (
        ("记住", "remember"),
        ("更正记忆", "correct"),
        ("忘记记忆", "forget"),
    ):
        if text.strip().startswith(prefix):
            return action, text.strip()[len(prefix) :].lstrip(" ：:")
    return None


def display(memory: Row) -> str:
    from kestri.memory.presentation import detail

    return detail(memory)


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

    async def apply(
        self,
        run: Row,
        *,
        instruction: tuple[str, str] | None = None,
        natural_override: NaturalMemoryControl | None = None,
    ) -> str:
        instruction = instruction or memory_instruction(run["request"])
        if run["kind"] != "memory_control" or instruction is None:
            raise PolicyDenied("MemoryAuthorizationUnavailable")
        action, body = instruction
        natural = natural_override or natural_control(run["request"])
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
                if action == "choose":
                    state = await (
                        await conn.execute(
                            "SELECT memory_choice,memory_epoch FROM kestri.conversations "
                            "WHERE chat_id = %s",
                            (run["chat_id"],),
                        )
                    ).fetchone()
                    choice = state["memory_choice"] if state else None
                    if (
                        not state
                        or not choice
                        or datetime.fromisoformat(choice["expires"]) <= datetime.now(UTC)
                        or choice["epoch"] != state["memory_epoch"]
                    ):
                        return "这个选择已经失效。请重新说明要纠正或忘记哪条记忆。"
                    if body.startswith("选择记忆 "):
                        _, token, number = body.split()
                        if token != choice["token"]:
                            return "这个选择已经失效，请重新发起记忆修改。"
                        index = int(number) - 1
                    else:
                        marker = re.search(r"[一二三四五1-5]", body)
                        assert marker is not None
                        index = (
                            "一二三四五".index(marker[0])
                            if marker[0] in "一二三四五"
                            else int(marker[0]) - 1
                        )
                    if index >= len(choice["targets"]):
                        return "没有这个选项，请从上次列出的目标中选择。"
                    selected = choice["targets"][index]
                    current_memory = await (
                        await conn.execute(
                            """
                            SELECT m.id FROM kestri.memories AS m
                            LEFT JOIN kestri.tasks AS t ON t.id = m.task_id
                            WHERE m.chat_id = %s AND m.id = %s AND m.revision = %s
                              AND m.status IN ('active','candidate')
                              AND (m.expires_at IS NULL OR m.expires_at > now())
                              AND (m.task_id IS NULL OR t.status != 'deleted')
                            """,
                            (run["chat_id"], selected["id"], selected["revision"]),
                        )
                    ).fetchone()
                    if not current_memory:
                        return "目标记忆已变更，这个选择不能继续。请重新发起修改。"
                    action, body = choice["action"], selected["id"]
                    if action == "correct":
                        body += " " + choice["content"]
                    natural = None
                    await conn.execute(
                        "UPDATE kestri.conversations SET memory_choice = NULL WHERE chat_id = %s",
                        (run["chat_id"],),
                    )
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
                    if natural:
                        body, notice = await self._resolve_target(
                            conn,
                            run,
                            natural.target,
                            allow_id=natural.id_target,
                            action=natural.action,
                            content=natural.content,
                        )
                        if body and natural.action == "correct":
                            body += " " + (natural.content or "")
                    parts = body.split(maxsplit=1)
                    if parts and re.fullmatch(r"[0-9a-f-]{8,36}", parts[0]):
                        targets = await (
                            await conn.execute(
                                (
                                    "SELECT * FROM kestri.memories WHERE chat_id=%s "
                                    "AND status IN ('active','candidate') AND id::text LIKE %s FOR "
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
                                    "已移出有效检索和对话上下文；自动提取不再使用此刻以前的聊天。"
                                    "历史仍保留。",
                                    True,
                                )
                            if changed:
                                await conn.execute(
                                    (
                                        "UPDATE kestri.memories SET status=%s,revision=revision+1,"
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
                    if action == "forget":
                        await conn.execute(
                            "UPDATE kestri.conversations SET automatic_history_floor="
                            "(SELECT COALESCE(max(id),0) FROM kestri.messages WHERE "
                            "chat_id=%s) WHERE chat_id=%s",
                            (run["chat_id"], run["chat_id"]),
                        )
                    await conn.execute(
                        (
                            "UPDATE kestri.conversations SET thread_id=NULL,memory_choice=NULL,"
                            "memory_revision=memory_revision+1,memory_epoch=memory_epoch+1,updated_at=now()"
                            " "
                            "WHERE chat_id=%s"
                        ),
                        (run["chat_id"],),
                    )
                await conn.execute(
                    ("INSERT INTO kestri.memory_changes(run_id,result) VALUES (%s,%s)"),
                    (run["id"], self.store.redactor.text(notice)),
                )
                return notice

    async def _resolve_target(
        self,
        conn: Any,
        run: Row,
        target: str,
        *,
        allow_id: bool = False,
        action: str = "forget",
        content: str | None = None,
    ) -> tuple[str, str]:
        """Only a unique literal owner target authorizes mutation; otherwise offer IDs."""
        limit = (
            self.settings.auto_memory_limit
            + self.settings.memory_limit
            + self.settings.memory_candidate_limit
        )
        rows = await (
            await conn.execute(
                """
                SELECT m.*
                FROM kestri.memories AS m
                LEFT JOIN kestri.tasks AS t ON t.id = m.task_id
                WHERE m.chat_id = %s
                  AND m.status IN ('active', 'candidate')
                  AND (m.expires_at IS NULL OR m.expires_at > now())
                  AND (m.task_id IS NULL OR t.status != 'deleted')
                ORDER BY m.updated_at DESC, m.id
                LIMIT %s
                """,
                (run["chat_id"], limit + 1),
            )
        ).fetchall()
        needle = normalize_target(target)
        if allow_id and re.fullmatch(r"[0-9a-f-]{8,36}", target.strip()):
            return needle, ""
        literal = [row for row in rows if needle in normalize_target(row["content"])]
        if len(needle) >= 2 and len(literal) == 1 and len(rows) <= limit:
            return str(literal[0]["id"]), ""
        suggestions = literal[:5] if len(needle) >= 2 else []
        if not suggestions:
            suggestions = lexical_rank(rows[:limit], target)[:5]
        if not suggestions:
            return "", "未作变更。没有找到明确目标；请用 /memory 查看，再提供记忆 ID。"
        state = await (
            await conn.execute(
                "SELECT memory_epoch FROM kestri.conversations WHERE chat_id = %s",
                (run["chat_id"],),
            )
        ).fetchone()
        choice = {
            "token": uuid4().hex[:16],
            "action": action,
            "content": content,
            "run_id": str(run["id"]),
            "epoch": state["memory_epoch"],
            "expires": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
            "targets": [{"id": str(r["id"]), "revision": r["revision"]} for r in suggestions],
        }
        await conn.execute(
            "UPDATE kestri.conversations SET memory_choice = %s WHERE chat_id = %s",
            (Jsonb(choice), run["chat_id"]),
        )
        lines = [
            "未作变更。请确认下面的目标，再发送 /correct ID 完整新内容 或 /forget ID：",
            "也可以回复“第二条”或点击对应按钮。选择在 10 分钟后失效。",
        ]
        for number, row in enumerate(suggestions, 1):
            scope = "个人" if row["task_id"] is None else "任务 " + str(row["task_id"])[:8]
            lines.append(f"{number}. {str(row['id'])[:8]} · {scope} · {row['content'][:120]}")
        if len(rows) > limit:
            lines.append("可选记忆超出检查上限；请使用明确 ID。")
        return "", "\n".join(lines)

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
                (
                    "SELECT count(*) AS n FROM kestri.memories WHERE chat_id=%s AND "
                    "status='active' AND origin='explicit_command'"
                ),
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
                    "status,supersedes,expires_at,last_source_message_id) VALUES (%s,%s,%s,%s,"
                    "%s,%s,%s,'active',%s,%s,(SELECT id FROM kestri.messages WHERE run_id=%s "
                    "AND direction='in' LIMIT 1)) RETURNING *"
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
                    run["id"],
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
                            "status='active' AND (expires_at<=now() OR review_after<=now()) "
                            "RETURNING id"
                        ),
                        (chat_id,),
                    )
                ).fetchall()
                if rows:
                    await conn.execute(
                        (
                            "UPDATE kestri.conversations SET thread_id=NULL,memory_choice=NULL,"
                            "memory_revision=memory_revision+1,memory_epoch=memory_epoch+1 "
                            "WHERE chat_id=%s"
                        ),
                        (chat_id,),
                    )

    async def retrieve(self, run: Row) -> list[Row]:
        state = await self.store.one(
            "SELECT memory_use_enabled FROM kestri.conversations WHERE chat_id=%s",
            (run["chat_id"],),
        )
        if state and not state["memory_use_enabled"]:
            return []
        # Always apply task scope; no automatic extraction from source messages or old summaries.
        rows = await self.store.all(
            (
                "SELECT m.* FROM kestri.memories m LEFT JOIN "
                "kestri.tasks t ON t.id=m.task_id WHERE "
                "m.chat_id=%s AND m.status='active' AND m.origin!='auto_inferred' AND "
                "(m.expires_at IS NULL OR m.expires_at>now()) AND "
                "(m.review_after IS NULL OR m.review_after>now()) AND "
                "(m.valid_from IS NULL OR m.valid_from<=now()) AND "
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
