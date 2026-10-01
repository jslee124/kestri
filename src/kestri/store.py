"""Durable inbox, runs, canonical archive, evidence, outbox, and usage ledger."""

from datetime import UTC, datetime
from importlib.resources import files
from typing import Any
from uuid import uuid4

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from kestri.errors import BudgetExceeded, PolicyDenied
from kestri.redaction import Redactor

Row = dict[str, Any]


def chunks(text: str, limit: int = 3500) -> list[str]:
    return [text[start : start + limit] for start in range(0, len(text), limit)] or ["（无内容）"]


class Store:
    def __init__(self, dsn: str, redactor: Redactor) -> None:
        self.redactor = redactor
        self.pool = AsyncConnectionPool[AsyncConnection[Row]](
            dsn,
            kwargs={
                "autocommit": True,
                "row_factory": dict_row,
                "prepare_threshold": 0,
                "connect_timeout": 10,
                "options": "-c statement_timeout=10000 -c lock_timeout=5000",
            },
            min_size=1,
            max_size=6,
            open=False,
            timeout=10,
        )

    async def open(self) -> None:
        await self.pool.open(wait=True, timeout=10)
        sql = files("kestri").joinpath("sql/001_initial.sql").read_text()
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtext('kestri-migrations'))")
                await conn.execute(sql, prepare=False)

    async def close(self) -> None:
        await self.pool.close()

    async def one(self, sql: str, params: tuple[Any, ...] = ()) -> Row | None:
        async with self.pool.connection() as conn:
            return await (await conn.execute(sql, params)).fetchone()

    async def all(self, sql: str, params: tuple[Any, ...] = ()) -> list[Row]:
        async with self.pool.connection() as conn:
            return await (await conn.execute(sql, params)).fetchall()

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
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
            "INSERT INTO kestri.meta VALUES ('offset',%s) ON CONFLICT (key) DO UPDATE "
            "SET value=to_jsonb(GREATEST((kestri.meta.value)::text::bigint,%s))",
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
    ) -> tuple[bool, str | None]:
        """Called only after authorization. Deduplication and state changes are atomic."""
        text = self.redactor.text(text)
        run_id: str | None = None
        async with self.pool.connection() as conn:
            async with conn.transaction():
                inserted = await (
                    await conn.execute(
                        "INSERT INTO kestri.inbox(update_id,chat_id,message_id) VALUES (%s,%s,%s) "
                        "ON CONFLICT DO NOTHING RETURNING update_id",
                        (update_id, chat_id, message_id),
                    )
                ).fetchone()
                if inserted is None:
                    return False, None
                await conn.execute(
                    "INSERT INTO kestri.conversations(chat_id) VALUES (%s) ON CONFLICT DO NOTHING",
                    (chat_id,),
                )
                await conn.execute(
                    "SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                    (chat_id,),
                )
                if command is None:
                    row = await (
                        await conn.execute(
                            "SELECT count(*) AS n FROM kestri.runs "
                            "WHERE chat_id=%s AND status IN ('queued','running')",
                            (chat_id,),
                        )
                    ).fetchone()
                    if row is not None and row["n"] >= queue_limit:
                        command = "queue_full"
                    else:
                        run_id = str(uuid4())
                        await conn.execute(
                            "INSERT INTO kestri.runs(id,chat_id,message_id"
                            ",request,reply_to,status) "
                            "VALUES (%s,%s,%s,%s,%s,'queued')",
                            (run_id, chat_id, message_id, text, reply_to),
                        )
                        await conn.execute(
                            "UPDATE kestri.inbox SET run_id=%s WHERE update_id=%s",
                            (run_id, update_id),
                        )
                await conn.execute(
                    "INSERT INTO kestri.messages(chat_id,telegram_"
                    "id,direction,content,reply_to,run_id)"
                    " VALUES (%s,%s,'in',%s,%s,%s) ON CONFLICT DO NOTHING",
                    (chat_id, message_id, text, reply_to, run_id),
                )
                if command == "stop":
                    if reply_to is not None:
                        target = await (
                            await conn.execute(
                                "SELECT r.id,r.status FROM kestri.messages m JOIN kestri.runs r "
                                "ON r.id=m.run_id WHERE m.chat_id=%s AND m.telegram_id=%s "
                                "ORDER BY m.id DESC LIMIT 1",
                                (chat_id, reply_to),
                            )
                        ).fetchone()
                    else:
                        target = await (
                            await conn.execute(
                                "SELECT id,status FROM kestri.runs WHERE "
                                "chat_id=%s AND status='running'"
                                " ORDER BY started_at LIMIT 1",
                                (chat_id,),
                            )
                        ).fetchone()
                    if target and target["status"] in {"queued", "running"}:
                        run_id = str(target["id"])
                        await conn.execute(
                            "UPDATE kestri.runs SET cancel_requested=true, "
                            "status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END "
                            "WHERE id=%s",
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
                elif command is not None:
                    notice = await self._command_notice(conn, command, chat_id)
                else:
                    notice = "已收到，正在处理。你可以用 /stop 停止当前执行。"
                await conn.execute(
                    "INSERT INTO kestri.outbox(id,chat_id,reply_to"
                    ",run_id,content) VALUES (%s,%s,%s,%s,%s)",
                    (uuid4(), chat_id, message_id, run_id, notice),
                )
        return True, run_id

    async def _command_notice(self, conn: Any, command: str, chat_id: int) -> str:
        if command in {"start", "help"}:
            return (
                "我是 Kestri。可以直接提问或让我查询公开网页，也可以回复之前的结果追问。\n"
                "/stop 停止当前执行；/status 查看状态；/runs 查看最近执行；/usage"
                " 查看本月估算用量。\n"
                "/new 新建对话上下文，保留原始记录。\n"
                "目前不支持持续任务或个人记忆。消息会通过 Telegram，研究内容会发送到 "
                "DeepSeek/Tavily。"
            )
        if command == "new":
            active = await (
                await conn.execute(
                    "SELECT id FROM kestri.runs WHERE chat_id=%s "
                    "AND status IN ('running','queued') "
                    "LIMIT 1",
                    (chat_id,),
                )
            ).fetchone()
            if active:
                return "当前仍有待处理或进行中请求。请先停止或等待完成，再用 /new 新建对话上下文。"
            await conn.execute(
                "UPDATE kestri.conversations SET thread_id=NULL WHERE chat_id=%s", (chat_id,)
            )
            return "已新建对话上下文；原始消息、历史结果和证据仍然保留。"
        if command in {"runs", "status"}:
            rows = await (
                await conn.execute(
                    "SELECT r.id,r.status,r.error_type, "
                    "(SELECT count(*) FROM kestri.evidence e WHERE e.run_id=r.id) AS evidence, "
                    "(SELECT count(*) FROM kestri.usage u WHERE u.run_id=r.id) AS calls, "
                    "(SELECT count(*) FROM kestri.outbox o WHERE o.run_id=r.id "
                    "AND o.status IN ('uncertain','failed')) AS delivery_problems "
                    "FROM kestri.runs r WHERE chat_id=%s ORDER BY created_at DESC LIMIT 5",
                    (chat_id,),
                )
            ).fetchall()
            return "最近执行：\n" + (
                "\n".join(
                    f"{str(row['id'])[:8]} · {row['status']}"
                    f" · 来源 {row['evidence']} · 操作 {row['calls']}"
                    f" · 发送待核对 {row['delivery_problems']}"
                    + (f" · {row['error_type']}" if row["error_type"] else "")
                    for row in rows
                )
                or "暂无执行。"
            )
        if command == "usage":
            row = await (
                await conn.execute(
                    "SELECT COALESCE(sum(amount_micro_usd),0) AS amount,count(*) AS calls "
                    "FROM kestri.usage WHERE "
                    "created_at>=date_trunc('month',now() AT TIME "
                    "ZONE 'UTC')"
                    " AT TIME ZONE 'UTC'"
                )
            ).fetchone()
            return (
                (
                    f"本月（UTC）本地估算/预留：${int(row['amount']) / 1_000_000:.4f}；"
                    f"{row['calls']} 次计费操作。此值不是服务商账单，未知请求保留预留额度。"
                )
                if row
                else "暂无用量。"
            )
        return "暂不支持该命令。使用 /help 查看当前能力。"

    async def claim_run(self) -> Row | None:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                row = await (
                    await conn.execute(
                        "SELECT * FROM kestri.runs WHERE status='queued' AND NOT cancel_requested "
                        "ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED"
                    )
                ).fetchone()
                if row is None:
                    return None
                conversation = await (
                    await conn.execute(
                        "SELECT thread_id FROM kestri.conversations WHERE chat_id=%s",
                        (row["chat_id"],),
                    )
                ).fetchone()
                row["source_thread"] = conversation["thread_id"] if conversation else None
                row["id"] = str(row["id"])
                await conn.execute(
                    "UPDATE kestri.runs SET status='running',started_at=now(),source_thread=%s "
                    "WHERE id=%s",
                    (row["source_thread"], row["id"]),
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
                        "SELECT chat_id FROM kestri.runs WHERE id=%s",
                        (run_id,),
                    )
                ).fetchone()
                if reference is None:
                    return
                # Match inbox control lock order: conversation first, then run.
                await conn.execute(
                    "SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                    (reference["chat_id"],),
                )
                row = await (
                    await conn.execute(
                        "SELECT * FROM kestri.runs WHERE id=%s FOR UPDATE", (run_id,)
                    )
                ).fetchone()
                if row is None or row["status"] != "running":
                    return
                if row["cancel_requested"]:
                    status, answer, error_type = "cancelled", "执行已停止。", "Cancelled"
                answer = self.redactor.text(answer)
                await conn.execute(
                    "UPDATE kestri.runs SET status=%s,result=%s,error_type=%s,finished_at=now() "
                    "WHERE id=%s",
                    (status, answer, error_type, run_id),
                )
                await conn.execute(
                    "UPDATE kestri.usage SET state='unknown' WHERE run_id=%s AND state='reserved'",
                    (run_id,),
                )
                if status == "completed":
                    await conn.execute(
                        "UPDATE kestri.conversations SET "
                        "thread_id=%s,updated_at=now() WHERE "
                        "chat_id=%s",
                        (run_id, row["chat_id"]),
                    )
                for part in chunks(answer):
                    await conn.execute(
                        "INSERT INTO kestri.outbox(id,chat_id,reply_to,run_id,content) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (uuid4(), row["chat_id"], row["message_id"], run_id, part),
                    )

    async def recover(self) -> None:
        rows = await self.all("SELECT id FROM kestri.runs WHERE status='running'")
        for row in rows:
            await self.finish(
                str(row["id"]),
                "interrupted",
                "上次执行因程序停止而中断，未自动重跑。请重新发送需要继续的请求。",
                "ProcessInterrupted",
            )
        await self.execute(
            "UPDATE kestri.outbox SET status='uncertain',error_type='ProcessInterrupted' "
            "WHERE status='sending'"
        )
        await self.execute("UPDATE kestri.usage SET state='unknown' WHERE state='reserved'")

    async def reply_context(self, chat_id: int, telegram_id: int) -> Row | None:
        return await self.one(
            "SELECT r.id,r.result,r.status FROM "
            "kestri.messages m JOIN kestri.runs r ON "
            "r.id=m.run_id "
            "WHERE m.chat_id=%s AND m.telegram_id=%s AND r.status='completed' "
            "ORDER BY m.id DESC LIMIT 1",
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
            "INSERT INTO kestri.evidence(id,run_id,kind,url,title,status,truncated,metadata) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
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

    async def reserve(self, run_id: str, kind: str, amount: int, monthly: int, per_run: int) -> str:
        reservation = str(uuid4())
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtext('kestri-budget'))")
                run = await (
                    await conn.execute(
                        "SELECT status,cancel_requested FROM kestri.runs WHERE id=%s", (run_id,)
                    )
                ).fetchone()
                if not run or run["status"] != "running" or run["cancel_requested"]:
                    raise PolicyDenied("RunInactive")
                month = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                total = await (
                    await conn.execute(
                        "SELECT COALESCE(sum(amount_micro_usd),0) AS amount FROM kestri.usage "
                        "WHERE created_at >= %s",
                        (month,),
                    )
                ).fetchone()
                local = await (
                    await conn.execute(
                        "SELECT COALESCE(sum(amount_micro_usd),0) AS "
                        "amount FROM kestri.usage WHERE run_id=%s",
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
                    "INSERT INTO "
                    "kestri.usage(id,run_id,kind,amount_micro_usd)"
                    " VALUES (%s,%s,%s,%s)",
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
                row = await (
                    await conn.execute(
                        "SELECT *,next_attempt<=now() AS ready FROM kestri.outbox WHERE "
                        "status='pending' "
                        "ORDER BY sequence LIMIT 1 FOR UPDATE SKIP LOCKED"
                    )
                ).fetchone()
                if row and row["ready"]:
                    await conn.execute(
                        "UPDATE kestri.outbox SET status='sending',attempts=attempts+1 WHERE id=%s",
                        (row["id"],),
                    )
                    row["attempts"] += 1
                    return row
                return None

    async def delivered(self, row: Row, telegram_id: int) -> None:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE kestri.outbox SET status='sent',telegram_id=%s WHERE id=%s",
                    (telegram_id, row["id"]),
                )
                await conn.execute(
                    "INSERT INTO kestri.messages(chat_id,telegram_"
                    "id,direction,content,reply_to,run_id)"
                    " VALUES (%s,%s,'out',%s,%s,%s) ON CONFLICT DO NOTHING",
                    (row["chat_id"], telegram_id, row["content"], row["reply_to"], row["run_id"]),
                )

    async def delivery_failed(
        self, row: Row, error_type: str, *, uncertain: bool, delay: int = 3
    ) -> None:
        status = "uncertain" if uncertain else ("pending" if row["attempts"] < 3 else "failed")
        await self.execute(
            "UPDATE kestri.outbox SET status=%s,error_type"
            "=%s,next_attempt=now()+make_interval(secs=>%s"
            ")"
            " WHERE id=%s",
            (status, error_type, max(1, min(delay, 120)), row["id"]),
        )
