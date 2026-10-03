"""Durable inbox, runs, canonical archive, evidence, outbox, and usage ledger."""

import re
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any
from uuid import uuid4

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composed
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from kestri.errors import BudgetExceeded, PolicyDenied
from kestri.redaction import Redactor

Row = dict[str, Any]


def chunks(text: str, limit: int = 3500) -> list[str]:
    return [text[start : start + limit] for start in range(0, len(text), limit)] or ["（无内容）"]


class Store:
    def __init__(self, dsn: str, redactor: Redactor) -> None:
        self.embedding_space: str | None = None
        self.owner_timezone: str | None = None
        self.redactor = redactor
        self.pool = AsyncConnectionPool[AsyncConnection[Row]](
            dsn,
            kwargs={
                "autocommit": True,
                "row_factory": dict_row,
                "prepare_threshold": 0,
                "connect_timeout": 10,
                "options": "-c statement_timeout=10000 -c lock_timeout=5000 -c search_path=public",
            },
            min_size=1,
            max_size=6,
            open=False,
            timeout=10,
        )

    async def open(self) -> None:
        await self.pool.open(wait=True, timeout=10)
        sql = files("kestri").joinpath("storage/sql/001_initial.sql").read_text()
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtext('kestri-migrations'))")
                await conn.execute(sql, prepare=False)
                await conn.execute(
                    files("kestri").joinpath("storage/sql/002_tasks.sql").read_text(),
                    prepare=False,
                )
                await conn.execute(
                    files("kestri").joinpath("storage/sql/003_memory_context.sql").read_text(),
                    prepare=False,
                )
                await conn.execute(
                    files("kestri").joinpath("storage/sql/004_data_lifecycle.sql").read_text(),
                    prepare=False,
                )
                await conn.execute(
                    files("kestri").joinpath("storage/sql/005_automatic_memory.sql").read_text(),
                    prepare=False,
                )
                await conn.execute(
                    files("kestri").joinpath("storage/sql/006_semantic_memory.sql").read_text(),
                    prepare=False,
                )
                await conn.execute(
                    files("kestri").joinpath("storage/sql/007_history_embeddings.sql").read_text(),
                    prepare=False,
                )
                await conn.execute(
                    files("kestri").joinpath("storage/sql/008_history_jobs.sql").read_text(),
                    prepare=False,
                )
                await conn.execute(
                    files("kestri").joinpath("storage/sql/009_checkpoint_schema.sql").read_text(),
                    prepare=False,
                )
                await conn.execute(
                    files("kestri").joinpath("storage/sql/010_memory_assistant.sql").read_text(),
                    prepare=False,
                )

    async def close(self) -> None:
        await self.pool.close()

    async def one(self, sql: str | SQL | Composed, params: tuple[Any, ...] = ()) -> Row | None:
        async with self.pool.connection() as conn:
            return await (await conn.execute(sql, params)).fetchone()

    async def all(self, sql: str | SQL | Composed, params: tuple[Any, ...] = ()) -> list[Row]:
        async with self.pool.connection() as conn:
            return await (await conn.execute(sql, params)).fetchall()

    async def execute(self, sql: str | SQL | Composed, params: tuple[Any, ...] = ()) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(sql, params)

    async def bind_identity(self, bot_id: int, owner_id: int) -> None:
        identity = {"bot_id": bot_id, "owner_id": owner_id}
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO kestri.meta VALUES ('identity',%s) ON CONFLICT DO NOTHING",
                    (Jsonb(identity),),
                )
                row = await (
                    await conn.execute(
                        "SELECT value FROM kestri.meta WHERE key='identity' FOR UPDATE"
                    )
                ).fetchone()
                if row is None or row["value"] != identity:
                    raise PolicyDenied("DatabaseIdentityMismatch")

    async def offset(self) -> int:
        row = await self.one("SELECT value FROM kestri.meta WHERE key='offset'")
        return int(row["value"]) if row else 0

    async def advance_offset(self, update_id: int) -> None:
        await self.execute(
            "INSERT INTO kestri.meta VALUES ('offset',%s) ON CONFLICT (key) DO UPDATE SET "
            "value=to_jsonb(GREATEST((kestri.meta.value)::text::bigint,%s))",
            (Jsonb(update_id + 1), update_id + 1),
        )

    async def accept(
        self,
        update_id: int,
        chat_id: int,
        message_id: int,
        text: str,
        reply_to: int | None,
        command: str | None,
        queue_limit: int,
        kind: str = "foreground",
        provenance: str = "direct",
    ) -> tuple[bool, str | None]:
        """Called only after authorization. Deduplication and state changes are atomic."""
        text = self.redactor.text(text)
        run_id: str | None = None
        async with self.pool.connection() as conn:
            async with conn.transaction():
                inserted = await (
                    await conn.execute(
                        (
                            "INSERT INTO kestri.inbox(update_id,chat_id,"
                            "message_id) VALUES (%s,%s,%s) ON CONFLICT DO "
                            "NOTHING RETURNING update_id"
                        ),
                        (update_id, chat_id, message_id),
                    )
                ).fetchone()
                if inserted is None:
                    return False, None
                await conn.execute(
                    (
                        "INSERT INTO kestri.conversations(chat_id) VALUES "
                        "(%s) ON CONFLICT DO NOTHING"
                    ),
                    (chat_id,),
                )
                await conn.execute(
                    ("SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE"),
                    (chat_id,),
                )
                if command is None:
                    row = await (
                        await conn.execute(
                            (
                                "SELECT count(*) AS n FROM kestri.runs WHERE "
                                "chat_id=%s AND kind NOT IN "
                                "('background','memory_maintenance') AND status IN "
                                "('queued','running')"
                            ),
                            (chat_id,),
                        )
                    ).fetchone()
                    if row is not None and row["n"] >= queue_limit:
                        command = "queue_full"
                    else:
                        run_id = str(uuid4())
                        await conn.execute(
                            (
                                "INSERT INTO kestri.runs(id,chat_id,message_id,"
                                "request,reply_to,status,kind) VALUES (%s,%s,%s,%s,"
                                "%s,'queued',%s)"
                            ),
                            (run_id, chat_id, message_id, text, reply_to, kind),
                        )
                        await conn.execute(
                            ("UPDATE kestri.inbox SET run_id=%s WHERE update_id=%s"),
                            (run_id, update_id),
                        )
                archived = await (
                    await conn.execute(
                        "INSERT INTO kestri.messages(chat_id,telegram_id,direction,content,"
                        "reply_to,run_id,provenance) VALUES (%s,%s,'in',%s,%s,%s,%s) "
                        "ON CONFLICT DO NOTHING RETURNING id",
                        (chat_id, message_id, text, reply_to, run_id, provenance),
                    )
                ).fetchone()
                if command is None and kind == "foreground":
                    await conn.execute(
                        """
                        UPDATE kestri.conversations SET memory_choice = NULL
                        WHERE chat_id = %s AND memory_choice->>'mode' = 'reference'
                        """,
                        (chat_id,),
                    )
                if archived and command is None and kind == "foreground" and provenance == "direct":
                    await conn.execute(
                        "INSERT INTO "
                        "kestri.memory_jobs(id,chat_id,source_message_id,settings_generation)"
                        " "
                        "SELECT %s,chat_id,%s,memory_settings_generation FROM kestri.conversations "
                        "WHERE chat_id=%s AND auto_memory_enabled",
                        (uuid4(), archived["id"], chat_id),
                    )
                if command == "stop":
                    stop_args = text.split(maxsplit=1)
                    if len(stop_args) == 2 and stop_args[0].split("@")[0].lower() == "/stop":
                        matches = await (
                            await conn.execute(
                                (
                                    "SELECT id,status FROM kestri.runs WHERE "
                                    "chat_id=%s AND status IN ('queued','running') AND "
                                    "id::text LIKE %s"
                                ),
                                (
                                    chat_id,
                                    stop_args[1].strip().replace("%", "").replace("_", "") + "%",
                                ),
                            )
                        ).fetchall()
                        target = (
                            matches[0]
                            if len(matches) == 1
                            and re.fullmatch(r"[0-9a-f-]{8,36}", stop_args[1].strip())
                            else None
                        )
                    elif reply_to is not None:
                        target = await (
                            await conn.execute(
                                (
                                    "SELECT r.id,r.status FROM kestri.messages m JOIN "
                                    "kestri.runs r ON r.id=m.run_id WHERE m.chat_id=%s "
                                    "AND m.telegram_id=%s ORDER BY m.id DESC LIMIT 1"
                                ),
                                (chat_id, reply_to),
                            )
                        ).fetchone()
                    else:
                        target = await (
                            await conn.execute(
                                (
                                    "SELECT id,status FROM kestri.runs WHERE "
                                    "chat_id=%s AND kind NOT IN "
                                    "('background','memory_maintenance') AND "
                                    "status='running' ORDER BY started_at LIMIT 1"
                                ),
                                (chat_id,),
                            )
                        ).fetchone()
                    if target and target["status"] in {"queued", "running"}:
                        run_id = str(target["id"])
                        await conn.execute(
                            (
                                "UPDATE kestri.runs SET cancel_requested=true, "
                                "status=CASE WHEN status='queued' THEN 'cancelled' "
                                "ELSE status END WHERE id=%s"
                            ),
                            (run_id,),
                        )
                        notice = (
                            "已请求停止这次执行，不再启动新的模型或工具调用。"
                            "已提交的外部请求可能仍计费。"
                        )
                    else:
                        notice = "没有找到对应的进行中执行；没有停止其他执行。"
                elif command == "queue_full":
                    notice = "待处理消息已达上限；此请求未启动。请稍后重发，或先停止当前执行。"
                elif command == "memory" and provenance != "direct" and len(text.split()) > 1:
                    notice = "记忆控制只接受主人的直接消息；未作变更。"
                elif command is not None:
                    notice = await self._command_notice(
                        conn,
                        command,
                        chat_id,
                        text,
                    )
                else:
                    notice = "已收到，正在处理。你可以用 /stop 停止当前执行。"
                from kestri.assistant.presentation import presentation
                from kestri.memory.presentation import current_presentation

                for part in chunks(notice):
                    await conn.execute(
                        (
                            "INSERT INTO kestri.outbox(id,chat_id,reply_to,"
                            "run_id,content,presentation) VALUES (%s,%s,%s,%s,%s,%s)"
                        ),
                        (
                            uuid4(),
                            chat_id,
                            message_id,
                            run_id,
                            part,
                            Jsonb(await current_presentation(conn, chat_id, part))
                            if command == "memory"
                            else (Jsonb(presentation(part)) if command is not None else None),
                        ),
                    )
        return True, run_id

    async def _command_notice(self, conn: Any, command: str, chat_id: int, text: str = "") -> str:
        if command == "memory":
            from kestri.memory.repository import memory_command

            return await memory_command(
                conn,
                chat_id,
                text,
                embedding_space=self.embedding_space,
                timezone=self.owner_timezone,
            )
        if command == "history":
            args = text.split()
            if len(args) > 1:
                if len(args) > 3 or not all(
                    a.isascii() and a.isdigit() and len(a) <= 18 for a in args[1:]
                ):
                    return "格式：/history [原始记录ID [字符偏移]]。"
                record = await (
                    await conn.execute(
                        (
                            "SELECT id,content,direction FROM kestri.messages "
                            "WHERE chat_id=%s AND id=%s"
                        ),
                        (chat_id, int(args[1])),
                    )
                ).fetchone()
                if not record:
                    return "记录不可用。"
                offset = int(args[2]) if len(args) == 3 else 0
                content = record["content"][offset : offset + 3000]
                more = (
                    f"\n继续：/history {record['id']} {offset + 3000}"
                    if len(record["content"]) > offset + 3000
                    else ""
                )
                return f"原始记录 {record['id']} · {record['direction']}（只读）：\n{content}{more}"
            rows = await (
                await conn.execute(
                    (
                        "SELECT id,direction,content,created_at FROM "
                        "kestri.messages WHERE chat_id=%s ORDER BY id DESC "
                        "LIMIT 10"
                    ),
                    (chat_id,),
                )
            ).fetchall()
            return "原始历史（只读，不加入模型上下文）：\n" + "\n".join(
                f"{r['id']} · {r['direction']} · {r['created_at'].isoformat()}\n"
                f"{r['content'][:500]}"
                for r in reversed(rows)
            )
        if command in {"remember", "correct", "forget"}:
            return "记忆指令需要完整内容或目标 ID；使用 /memory 查看。"
        if command == "tasks":
            from kestri.tasks.presentation import view as task_view

            return await task_view(conn, chat_id, text)
        if command in {"start", "help", "status", "runs", "usage"}:
            from kestri.assistant.views import view as assistant_view

            return await assistant_view(conn, command, chat_id, text, self.owner_timezone)
        if command == "task":
            return "请说明完整任务，例如：每天早上八点给我 AI 新闻简报。"
        if command == "clarify":
            return "请分别发送任务修改、记忆设置或运行控制。本次没有作变更。"
        if command == "denied":
            return "控制只接受主人的直接消息；未作变更。"
        if command == "new":
            active = await (
                await conn.execute(
                    (
                        "SELECT id FROM kestri.runs WHERE chat_id=%s AND "
                        "kind NOT IN ('background','memory_maintenance') AND status IN ('running',"
                        "'queued') LIMIT 1"
                    ),
                    (chat_id,),
                )
            ).fetchone()
            if active:
                return "当前仍有待处理或进行中请求。请先停止或等待完成，再用 /new 新建对话上下文。"
            await conn.execute(
                (
                    "UPDATE kestri.conversations SET thread_id=NULL,memory_choice=NULL "
                    "WHERE chat_id=%s"
                ),
                (chat_id,),
            )
            return "已新建对话上下文；原始消息、历史结果和证据仍然保留。"
        return "暂不支持该命令。使用 /help 查看当前能力。"

    async def claim_run(self, background: bool = False) -> Row | None:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                if background:
                    await conn.execute(
                        "SELECT chat_id FROM kestri.conversations ORDER BY chat_id FOR UPDATE"
                    )
                    await conn.execute(
                        "UPDATE kestri.runs r SET status='cancelled',"
                        "cancel_requested=true,finished_at=now(),"
                        "error_type='CatchUpExpiredOrChanged' FROM "
                        "kestri.tasks t WHERE r.task_id=t.id AND "
                        "r.status='queued' AND r.kind='background' AND "
                        "(t.status!='active' OR "
                        "t.revision!=r.task_revision OR "
                        "r.scheduled_for+make_interval(secs=>t.catch_up_seconds)<now())"
                    )
                row = await (
                    await conn.execute(
                        (
                            "SELECT * FROM kestri.runs WHERE status='queued' "
                            "AND NOT cancel_requested AND available_at<=now() "
                            "AND kind!='memory_maintenance' AND (kind='background')=%s ORDER "
                            "BY created_at "
                            "LIMIT 1 FOR UPDATE SKIP LOCKED"
                        ),
                        (background,),
                    )
                ).fetchone()
                if row is None:
                    return None
                conversation = await (
                    await conn.execute(
                        (
                            "SELECT thread_id,memory_epoch FROM "
                            "kestri.conversations WHERE chat_id=%s"
                        ),
                        (row["chat_id"],),
                    )
                ).fetchone()
                row["source_thread"] = (
                    conversation["thread_id"]
                    if conversation and row["kind"] == "foreground"
                    else None
                )
                row["memory_epoch"] = conversation["memory_epoch"] if conversation else 0
                row["id"] = str(row["id"])
                await conn.execute(
                    (
                        "UPDATE kestri.runs SET status='running',"
                        "started_at=now(),source_thread=%s,memory_epoch=%s "
                        "WHERE id=%s"
                    ),
                    (row["source_thread"], row["memory_epoch"], row["id"]),
                )
                return row

    async def cancelled(self, run_id: str) -> bool:
        row = await self.one("SELECT cancel_requested FROM kestri.runs WHERE id=%s", (run_id,))
        return row is None or bool(row["cancel_requested"])

    async def finish(
        self,
        run_id: str,
        status: str,
        answer: str,
        error_type: str | None = None,
    ) -> None:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                reference = await (
                    await conn.execute(
                        ("SELECT chat_id FROM kestri.runs WHERE id=%s"),
                        (run_id,),
                    )
                ).fetchone()
                if reference is None:
                    return
                # Match inbox control lock order: conversation first, then run.
                await conn.execute(
                    ("SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE"),
                    (reference["chat_id"],),
                )
                row = await (
                    await conn.execute(
                        ("SELECT * FROM kestri.runs WHERE id=%s FOR UPDATE"), (run_id,)
                    )
                ).fetchone()
                if row is None or row["status"] != "running":
                    return
                if row["cancel_requested"]:
                    status, answer, error_type = (
                        "cancelled",
                        "执行已停止。",
                        "Cancelled",
                    )
                if status == "completed" and row["kind"] in {
                    "foreground",
                    "background",
                }:
                    epoch = await (
                        await conn.execute(
                            "SELECT memory_epoch FROM kestri.conversations WHERE chat_id=%s",
                            (row["chat_id"],),
                        )
                    ).fetchone()
                    if epoch and row["memory_epoch"] != epoch["memory_epoch"]:
                        status, answer, error_type = (
                            "failed",
                            "有效记忆已变更，此次旧上下文执行已停止。请重新发送需要继续的请求。",
                            "MemoryContextChanged",
                        )
                if row["kind"] in {"task_control", "memory_control"}:
                    change = await (
                        await conn.execute(
                            (
                                "SELECT result FROM kestri.task_changes WHERE "
                                "run_id=%s UNION ALL SELECT result FROM "
                                "kestri.memory_changes WHERE run_id=%s"
                            ),
                            (run_id, run_id),
                        )
                    ).fetchone()
                    if change:
                        status, answer, error_type = "completed", change["result"], None
                if (
                    row["kind"] == "background"
                    and status == "failed"
                    and error_type
                    in {
                        "APIConnectionError",
                        "APITimeoutError",
                        "RateLimitError",
                        "InternalServerError",
                        "ConnectError",
                        "ConnectTimeout",
                        "PoolTimeout",
                    }
                    and row["attempt"] < 2
                ):
                    task = await (
                        await conn.execute(
                            ("SELECT status,revision FROM kestri.tasks WHERE id=%s"),
                            (row["task_id"],),
                        )
                    ).fetchone()
                    if (
                        task
                        and task["status"] == "active"
                        and task["revision"] == row["task_revision"]
                    ):
                        await conn.execute(
                            (
                                "UPDATE kestri.runs SET status='queued',"
                                "attempt=attempt+1,available_at=now()+interval '30 "
                                "seconds',error_type=%s WHERE id=%s"
                            ),
                            (error_type, run_id),
                        )
                        await conn.execute(
                            (
                                "UPDATE kestri.usage SET state='unknown' WHERE "
                                "run_id=%s AND state='reserved'"
                            ),
                            (run_id,),
                        )
                        return
                if row["kind"] == "background":
                    answer = (
                        f"持续任务 {str(row['task_id'])[:8]} · 执行 {run_id[:8]} · {status}\n"
                        + answer
                    )
                answer = self.redactor.text(answer)
                await conn.execute(
                    (
                        "UPDATE kestri.runs SET status=%s,result=%s,"
                        "error_type=%s,finished_at=now() WHERE id=%s"
                    ),
                    (status, answer, error_type, run_id),
                )
                await conn.execute(
                    (
                        "UPDATE kestri.usage SET state='unknown' WHERE "
                        "run_id=%s AND state='reserved'"
                    ),
                    (run_id,),
                )
                if status == "completed" and row["kind"] == "foreground":
                    await conn.execute(
                        (
                            "UPDATE kestri.conversations SET thread_id=%s,"
                            "updated_at=now() WHERE chat_id=%s AND "
                            "memory_epoch=%s"
                        ),
                        (run_id, row["chat_id"], row["memory_epoch"]),
                    )
                from kestri.assistant.presentation import result_presentation

                choice_row = await (
                    await conn.execute(
                        "SELECT memory_choice FROM kestri.conversations WHERE chat_id = %s",
                        (row["chat_id"],),
                    )
                ).fetchone()
                choice = choice_row["memory_choice"] if choice_row else None
                if choice and choice.get("run_id") != str(run_id):
                    choice = None
                for part in chunks(answer):
                    display = await result_presentation(conn, row, status, part, choice)
                    await conn.execute(
                        (
                            "INSERT INTO kestri.outbox(id,chat_id,reply_to,"
                            "run_id,content,task_id,presentation) VALUES (%s,%s,%s,%s,%s,%s,%s)"
                        ),
                        (
                            uuid4(),
                            row["chat_id"],
                            None if row["kind"] == "background" else row["message_id"],
                            run_id,
                            part,
                            row["task_id"],
                            Jsonb(display) if display else None,
                        ),
                    )

    async def recover(self) -> None:
        rows = await self.all(
            "SELECT id FROM kestri.runs WHERE status='running' AND kind!='memory_maintenance'"
        )
        for row in rows:
            change = await self.one(
                (
                    "SELECT result FROM kestri.task_changes WHERE "
                    "run_id=%s UNION ALL SELECT result FROM "
                    "kestri.memory_changes WHERE run_id=%s"
                ),
                (row["id"], row["id"]),
            )
            if change:
                await self.finish(str(row["id"]), "completed", change["result"])
                continue
            await self.finish(
                str(row["id"]),
                "interrupted",
                "上次执行因程序停止而中断，未自动重跑。请重新发送需要继续的请求。",
                "ProcessInterrupted",
            )
        await self.execute(
            "UPDATE kestri.outbox SET status='uncertain',"
            "error_type='ProcessInterrupted' WHERE "
            "status='sending'"
        )
        await self.execute("UPDATE kestri.usage SET state='unknown' WHERE state='reserved'")

    async def reply_context(self, chat_id: int, telegram_id: int) -> Row | None:
        return await self.one(
            (
                "SELECT r.id,r.result,r.status FROM "
                "kestri.messages m JOIN kestri.runs r ON "
                "r.id=m.run_id JOIN kestri.conversations c ON "
                "c.chat_id=r.chat_id WHERE m.chat_id=%s AND "
                "m.telegram_id=%s AND r.status='completed' AND "
                "r.kind IN ('foreground','background') AND NOT r.history_expired AND "
                "r.memory_epoch=c.memory_epoch ORDER BY m.id DESC "
                "LIMIT 1"
            ),
            (chat_id, telegram_id),
        )

    async def add_evidence(
        self,
        run_id: str,
        kind: str,
        url: str,
        title: str,
        status: str,
        truncated: bool,
        metadata: Row,
        evidence_id: str | None = None,
    ) -> str:
        evidence_id = evidence_id or str(uuid4())
        await self.execute(
            "INSERT INTO "
            "kestri.evidence(id,run_id,kind,url,title,status,truncated,metadata) VALUES "
            "(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                evidence_id,
                run_id,
                kind,
                self.redactor.text(url),
                self.redactor.text(title[:300]),
                status,
                truncated,
                Jsonb(self.redactor.data(metadata)),
            ),
        )
        return evidence_id

    async def event(self, run_id: str, kind: str, metadata: Row) -> None:
        await self.execute(
            "INSERT INTO kestri.events(run_id,kind,metadata) VALUES (%s,%s,%s)",
            (run_id, kind, Jsonb(self.redactor.data(metadata))),
        )

    async def reserve(
        self,
        run_id: str,
        kind: str,
        amount: int,
        monthly: int,
        per_run: int,
        *,
        maintenance_monthly: int | None = None,
        maintenance_job: tuple[str, str] | None = None,
        index_job: tuple[str, str] | None = None,
        history_job: tuple[str, str, int] | None = None,
    ) -> str:
        reservation = str(uuid4())
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtext('kestri-budget'))")
                if maintenance_job is not None or index_job is not None or history_job is not None:
                    await conn.execute(
                        "SELECT c.chat_id FROM kestri.conversations c JOIN kestri.runs r ON "
                        "r.chat_id=c.chat_id "
                        "WHERE r.id=%s FOR UPDATE OF c",
                        (run_id,),
                    )
                    if history_job is not None:
                        allowed = await (
                            await conn.execute(
                                "SELECT 1 FROM kestri.history_index_jobs j JOIN "
                                "kestri.conversations c ON c.chat_id=j.chat_id JOIN "
                                "kestri.messages m ON m.id=j.owner_message_id JOIN "
                                "kestri.runs s ON s.id=m.run_id WHERE j.id=%s "
                                "AND j.lease_token=%s AND j.source_revision=%s AND j.run_id=%s "
                                "AND j.status='running' AND j.lease_until>now() "
                                "AND c.auto_memory_enabled AND c.memory_use_enabled "
                                "AND c.memory_semantic_enabled "
                                "AND c.memory_settings_generation=j.settings_generation "
                                "AND c.memory_retrieval_generation=j.retrieval_generation "
                                "AND c.memory_embedding_space=j.embedding_space "
                                "AND m.id>GREATEST(c.memory_activation_watermark,"
                                "c.automatic_history_floor) AND m.provenance='direct' "
                                "AND m.direction='in' AND s.kind='foreground' AND NOT "
                                "s.history_expired "
                                "AND (m.task_id IS NULL OR EXISTS(SELECT 1 FROM kestri.tasks "
                                "WHERE id=m.task_id AND status!='deleted'))",
                                (*history_job, run_id),
                            )
                        ).fetchone()
                        if not allowed:
                            raise PolicyDenied("HistoryJobChanged")
                    elif index_job is not None:
                        allowed = await (
                            await conn.execute(
                                "SELECT 1 FROM kestri.memory_index_jobs j JOIN "
                                "kestri.conversations c "
                                "ON c.chat_id=j.chat_id JOIN kestri.memories m ON m.id=j.memory_id "
                                "WHERE j.id=%s AND j.lease_token=%s AND j.run_id=%s "
                                "AND j.status='running' AND j.lease_until>now() "
                                "AND c.memory_use_enabled AND c.memory_semantic_enabled "
                                "AND c.memory_retrieval_generation=j.generation "
                                "AND c.memory_embedding_space=j.embedding_space "
                                "AND m.status='active' AND m.origin!='auto_inferred' "
                                "AND m.revision=j.revision "
                                "AND md5(m.content)=j.content_hash "
                                "AND (m.expires_at IS NULL OR m.expires_at>now()) "
                                "AND (m.review_after IS NULL OR m.review_after>now())",
                                (*index_job, run_id),
                            )
                        ).fetchone()
                        if not allowed:
                            raise PolicyDenied("MemoryIndexChanged")
                    else:
                        assert maintenance_job is not None
                        allowed = await (
                            await conn.execute(
                                "SELECT 1 FROM kestri.memory_jobs j JOIN kestri.conversations c "
                                "ON c.chat_id=j.chat_id "
                                "JOIN kestri.messages m ON m.id=j.source_message_id WHERE j.id=%s"
                                " AND j.lease_token=%s "
                                "AND j.run_id=%s AND j.status='running' AND j.lease_until>now() "
                                "AND c.auto_memory_enabled "
                                "AND j.settings_generation=c.memory_settings_generation AND "
                                "j.captured_revision=c.memory_revision "
                                "AND j.captured_epoch=c.memory_epoch AND "
                                "m.id>GREATEST(c.memory_activation_watermark,c.automatic_hi"
                                "story_floor)",
                                (*maintenance_job, run_id),
                            )
                        ).fetchone()
                        if not allowed:
                            raise PolicyDenied("MemoryJobChanged")
                run = await (
                    await conn.execute(
                        "SELECT status,cancel_requested,kind FROM kestri.runs WHERE id=%s",
                        (run_id,),
                    )
                ).fetchone()
                if not run or run["status"] != "running" or run["cancel_requested"]:
                    raise PolicyDenied("RunInactive")
                if run["kind"] == "memory_maintenance" and (
                    (maintenance_job is None and index_job is None and history_job is None)
                    or maintenance_monthly is None
                ):
                    raise PolicyDenied("MaintenanceBudgetUnavailable")
                month = datetime.now(UTC).replace(
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                total = await (
                    await conn.execute(
                        "SELECT COALESCE(sum(amount_micro_usd),0) AS amount FROM kestri.usage "
                        "WHERE created_at >= %s",
                        (month,),
                    )
                ).fetchone()
                if maintenance_monthly is not None:
                    used = await (
                        await conn.execute(
                            "SELECT COALESCE(sum(amount_micro_usd),0) AS amount FROM kestri.usage "
                            "WHERE created_at >= %s AND kind IN "
                            "('memory_extract','memory_index','history_index')",
                            (month,),
                        )
                    ).fetchone()
                    if used is None or used["amount"] + amount > maintenance_monthly:
                        raise BudgetExceeded("MaintenanceMonthlyBudgetExceeded")
                local = await (
                    await conn.execute(
                        "SELECT COALESCE(sum(amount_micro_usd),0) AS amount FROM kestri.usage "
                        "WHERE run_id=%s",
                        (run_id,),
                    )
                ).fetchone()
                if (
                    total is None
                    or local is None
                    or total["amount"] + amount > monthly
                    or local["amount"] + amount > per_run
                ):
                    raise BudgetExceeded("EstimatedBudgetExceeded")
                await conn.execute(
                    "INSERT INTO kestri.usage(id,run_id,kind,amount_micro_usd) VALUES "
                    "(%s,%s,%s,%s)",
                    (reservation, run_id, kind, amount),
                )
        return reservation

    async def settle(self, reservation: str, metadata: Row, amount: int | None = None) -> None:
        await self.execute(
            "UPDATE kestri.usage SET state='recorded',metadata=%s, "
            "amount_micro_usd=COALESCE(%s,amount_micro_usd) WHERE id=%s",
            (Jsonb(self.redactor.data(metadata)), amount, reservation),
        )

    async def claim_delivery(self) -> Row | None:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                while True:
                    row = await (
                        await conn.execute(
                            """
                            SELECT *, next_attempt <= now() AS ready
                            FROM kestri.outbox
                            WHERE status = 'pending'
                            ORDER BY sequence
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED
                            """
                        )
                    ).fetchone()
                    if not row or not row["ready"]:
                        return None
                    if not await self._delivery_current(conn, row):
                        await conn.execute(
                            """
                            UPDATE kestri.outbox
                            SET status = 'failed', content = '', presentation = NULL,
                                error_type = 'MemoryNoticeRevoked'
                            WHERE id = %s
                            """,
                            (row["id"],),
                        )
                        continue
                    await conn.execute(
                        "UPDATE kestri.outbox SET status='sending',attempts=attempts+1 WHERE id=%s",
                        (row["id"],),
                    )
                    row["attempts"] += 1
                    return row

    async def _delivery_current(self, conn: Any, row: Row) -> bool:
        """Recheck published automatic notices against current consent and source facts."""
        display = row.get("presentation")
        if display and "epoch" in display:
            current = await (
                await conn.execute(
                    "SELECT memory_epoch FROM kestri.conversations WHERE chat_id = %s",
                    (row["chat_id"],),
                )
            ).fetchone()
            if not current or current["memory_epoch"] != display["epoch"]:
                return False
        if row["run_id"] is None:
            return True
        state = await (
            await conn.execute(
                """
                SELECT r.kind,
                       r.status = 'completed'
                       AND j.status = 'succeeded'
                       AND c.auto_memory_enabled
                       AND c.memory_use_enabled
                       AND c.memory_settings_generation = j.settings_generation
                       AND c.memory_epoch = r.memory_epoch + CASE WHEN EXISTS (
                           SELECT 1 FROM kestri.memory_events AS e
                           WHERE e.job_id = j.id AND e.operation = 'replace'
                       ) THEN 1 ELSE 0 END
                       AND EXISTS (
                           SELECT 1 FROM kestri.memory_events AS e
                           WHERE e.job_id = j.id AND e.operation IN ('create', 'replace')
                       )
                       AND NOT EXISTS (
                           SELECT 1
                           FROM kestri.memory_events AS e
                           LEFT JOIN kestri.memories AS m ON m.id = e.memory_id
                           LEFT JOIN kestri.tasks AS t ON t.id = m.task_id
                           WHERE e.job_id = j.id
                             AND e.operation IN ('create', 'replace')
                             AND (
                                 m.id IS NULL OR m.status != 'active'
                                 OR m.origin = 'auto_inferred'
                                 OR (m.expires_at IS NOT NULL AND m.expires_at <= now())
                                 OR (m.review_after IS NOT NULL AND m.review_after <= now())
                                 OR (m.valid_from IS NOT NULL AND m.valid_from > now())
                                 OR (m.task_id IS NOT NULL AND t.status = 'deleted')
                             )
                       ) AS notice_current
                FROM kestri.runs AS r
                LEFT JOIN kestri.memory_jobs AS j ON j.run_id = r.id
                LEFT JOIN kestri.conversations AS c ON c.chat_id = r.chat_id
                WHERE r.id = %s
                """,
                (row["run_id"],),
            )
        ).fetchone()
        return bool(state and (state["kind"] != "memory_maintenance" or state["notice_current"]))

    async def delivery_current(self, row: Row) -> bool:
        # HTTP cannot be atomic with a database transaction; recheck immediately before send.
        async with self.pool.connection() as conn:
            allowed = await self._delivery_current(conn, row)
        if not allowed:
            await self.execute(
                """
                UPDATE kestri.outbox
                SET status = 'failed', content = '', presentation = NULL,
                                error_type = 'MemoryNoticeRevoked'
                WHERE id = %s AND status IN ('pending', 'sending')
                """,
                (row["id"],),
            )
        return allowed

    async def delivered(self, row: Row, telegram_id: int) -> None:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE kestri.outbox SET status='sent',telegram_id=%s WHERE id=%s",
                    (telegram_id, row["id"]),
                )
                await conn.execute(
                    "INSERT INTO "
                    "kestri.messages(chat_id,telegram_id,direction,content,reply_to,run_id,"
                    "task_id,provenance)"
                    " VALUES (%s,%s,'out',%s,%s,%s,%s,'context') ON CONFLICT DO NOTHING",
                    (
                        row["chat_id"],
                        telegram_id,
                        row["content"],
                        row["reply_to"],
                        row["run_id"],
                        row["task_id"],
                    ),
                )

    async def delivery_failed(
        self, row: Row, error_type: str, *, uncertain: bool, delay: int = 3
    ) -> None:
        if uncertain:
            status = "uncertain"
        elif row["attempts"] < 3:
            status = "pending"
        else:
            status = "failed"
        await self.execute(
            "UPDATE kestri.outbox SET "
            "status=%s,error_type=%s,next_attempt=now()+make_interval(secs=>%s) WHERE id=%s",
            (status, error_type, max(1, min(delay, 120)), row["id"]),
        )
