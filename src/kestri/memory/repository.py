"""Durable opt-in extraction jobs and transactional publication of validated memories."""

from typing import Any
from uuid import uuid4

from kestri.errors import PolicyDenied
from kestri.memory.extractor import (
    ExistingMemory,
    ExtractionBatch,
    MemoryProposal,
    MemorySource,
    ValidatedExtraction,
    validate_proposal,
)
from kestri.settings import ResearchSettings
from kestri.storage.store import Row, Store


async def memory_command(
    conn: Any,
    chat_id: int,
    text: str,
    *,
    embedding_space: str | None = None,
    timezone: str | None = None,
) -> str:
    args = text.strip().split()[1:]
    if len(args) == 2 and args[0] in {"use", "semantic"} and args[1] in {"on", "off"}:
        enabled = args[1] == "on"
        semantic = args[0] == "semantic"
        if semantic and enabled:
            ready = await (
                await conn.execute("SELECT to_regclass('kestri.memory_embeddings') AS name")
            ).fetchone()
            if not embedding_space or not ready or not ready["name"]:
                return "未开启：需要配置 DashScope embedding 并安装 pgvector；见语义记忆部署文档。"
        state = await (
            await conn.execute(
                "SELECT * FROM kestri.conversations WHERE chat_id=%s FOR UPDATE", (chat_id,)
            )
        ).fetchone()
        column = "memory_semantic_enabled" if semantic else "memory_use_enabled"
        assert state is not None
        if state[column] == enabled and (
            not semantic or not enabled or state["memory_embedding_space"] == embedding_space
        ):
            return "设置未变更。"
        # Column is an application constant, never user-supplied SQL.
        await conn.execute(
            "UPDATE kestri.conversations SET " + column + "=%s,"
            "memory_embedding_space=CASE WHEN %s THEN %s ELSE memory_embedding_space END,"
            "memory_retrieval_generation=memory_retrieval_generation+1,"
            "memory_revision=memory_revision+1,memory_epoch=memory_epoch+1,"
            "thread_id=NULL,memory_choice=NULL "
            "WHERE chat_id=%s",
            (enabled, semantic and enabled, embedding_space, chat_id),
        )
        await conn.execute(
            "UPDATE kestri.memory_index_jobs SET status='cancelled',"
            "lease_until=NULL,error_type='SettingsChanged',updated_at=now() WHERE chat_id=%s "
            "AND status IN ('queued','running','retry_wait')",
            (chat_id,),
        )
        await conn.execute(
            "UPDATE kestri.runs SET status='cancelled',cancel_requested=true,"
            "finished_at=now() WHERE status='running' AND id IN "
            "(SELECT run_id FROM kestri.memory_index_jobs WHERE chat_id=%s AND status='cancelled')",
            (chat_id,),
        )
        await conn.execute(
            "UPDATE kestri.usage SET state='unknown' WHERE state='reserved' AND run_id IN "
            "(SELECT run_id FROM kestri.memory_index_jobs WHERE chat_id=%s AND status='cancelled')",
            (chat_id,),
        )
        if enabled:
            # Trigger queues existing active facts only, never raw-history extraction.
            await conn.execute(
                "UPDATE kestri.memories SET updated_at=updated_at WHERE chat_id=%s "
                "AND status='active'",
                (chat_id,),
            )
        return (
            "已开启语义召回。\n\n有效记忆、合格历史片段与查询将发送到北京 DashScope，"
            "事实候选筛选使用 DeepSeek。"
            "\n不会自动提取旧聊天的新记忆。可以告诉我关闭语义检索。"
            if semantic and enabled
            else "已关闭语义召回。\n\n保留本地索引，回答时使用关键词检索。"
            if semantic
            else "已开启记忆使用。"
            if enabled
            else "已关闭记忆使用。\n\n停止在回答中使用记忆，也停止索引调用。\n"
            "自动记录是独立设置，需要时可以告诉我关闭自动记忆。"
        ) + "\n新的回答将使用更新后的设置。"
    if len(args) == 2 and args[0] == "auto" and args[1] in {"on", "off"}:
        enabled = args[1] == "on"
        current = await (
            await conn.execute(
                "SELECT auto_memory_enabled FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                (chat_id,),
            )
        ).fetchone()
        if current and current["auto_memory_enabled"] == enabled:
            return "自动记忆已开启。" if enabled else "自动记忆已关闭。"
        await conn.execute(
            "UPDATE kestri.conversations SET auto_memory_enabled=%s,"
            "memory_settings_generation=memory_settings_generation+1,"
            "memory_epoch=memory_epoch+1,thread_id=NULL,memory_choice=NULL,"
            "memory_activation_watermark=CASE WHEN %s THEN "
            "(SELECT COALESCE(max(id),0) FROM kestri.messages WHERE chat_id=%s) "
            "ELSE memory_activation_watermark END WHERE chat_id=%s",
            (enabled, enabled, chat_id, chat_id),
        )
        await conn.execute(
            "UPDATE kestri.memory_jobs SET status='cancelled',error_type='SettingsChanged',"
            "lease_until=NULL,updated_at=now() WHERE chat_id=%s "
            "AND status IN ('queued','running','retry_wait')",
            (chat_id,),
        )
        await conn.execute(
            "UPDATE kestri.runs SET cancel_requested=true,status='cancelled',finished_at=now() "
            "WHERE kind='memory_maintenance' AND chat_id=%s AND status='running'",
            (chat_id,),
        )
        await conn.execute(
            "UPDATE kestri.usage SET state='unknown' WHERE state='reserved' AND run_id IN "
            "(SELECT id FROM kestri.runs WHERE chat_id=%s AND kind='memory_maintenance' "
            "AND status='cancelled')",
            (chat_id,),
        )
        return (
            "已开启自动记忆。\n\n只处理之后的直接聊天，发送到 DeepSeek 整理；"
            "旧历史不会自动提取。\n开启后的聊天也可按需用于回答历史问题。"
            "\n可以随时告诉我关闭自动记忆。"
            if enabled
            else "已关闭自动记忆。\n\n之后的聊天不再自动生成新记忆，历史检索已暂停。"
            "已有记忆仍可用于回答，当前对话上下文已重置。"
        )
    if sum(part.startswith("/memory") for part in text.split()) > 1:
        return (
            "这条消息包含多条命令，需要分别发送。\n本次没有修改设置。\n\n"
            "先发送：\n/memory auto on\n\n再单独发送：\n/memory semantic on"
        )
    if args and args[0] == "why":
        from kestri.memory.diagnostics import explain

        return (
            await explain(conn, chat_id, args[1] if len(args) == 2 else None)
            if len(args) <= 2
            else "请只提供一个回答编号。"
        )
    from kestri.memory.views import view

    return await view(conn, chat_id, args, timezone)


class MemoryRepository:
    def __init__(self, store: Store, settings: ResearchSettings) -> None:
        self.store = store
        self.settings = settings

    async def claim(self, chat_id: int) -> Row | None:
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                state = await (
                    await conn.execute(
                        "SELECT * FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                        (chat_id,),
                    )
                ).fetchone()
                if not state or not state["auto_memory_enabled"]:
                    return None
                busy = await (
                    await conn.execute(
                        "SELECT 1 FROM kestri.runs WHERE chat_id=%s AND kind NOT IN "
                        "('background','memory_maintenance') AND status IN "
                        "('queued','running') LIMIT 1",
                        (chat_id,),
                    )
                ).fetchone()
                if busy:
                    return None
                job = await (
                    await conn.execute(
                        "SELECT *,available_at<=now() AS ready,lease_until>now() AS leased "
                        "FROM kestri.memory_jobs WHERE chat_id=%s AND status IN "
                        "('queued','running','retry_wait') ORDER BY source_message_id NULLS "
                        "FIRST,created_at "
                        "LIMIT 1 FOR UPDATE",
                        (chat_id,),
                    )
                ).fetchone()
                if not job or not job["ready"] or (job["status"] == "running" and job["leased"]):
                    return None
                cutoff = max(state["memory_activation_watermark"], state["automatic_history_floor"])
                if (
                    job["settings_generation"] != state["memory_settings_generation"]
                    or job["source_message_id"] is None
                    or job["source_message_id"] <= cutoff
                    or job["attempts"] >= 3
                ):
                    await conn.execute(
                        "UPDATE kestri.memory_jobs SET "
                        "status='cancelled',lease_until=NULL,error_type='JobIneligible',"
                        "updated_at=now() WHERE id=%s",
                        (job["id"],),
                    )
                    if job["run_id"]:
                        await conn.execute(
                            "UPDATE kestri.runs SET status='cancelled',cancel_requested=true,"
                            "finished_at=now() WHERE id=%s",
                            (job["run_id"],),
                        )
                        await conn.execute(
                            "UPDATE kestri.usage SET state='unknown' WHERE run_id=%s "
                            "AND state='reserved'",
                            (job["run_id"],),
                        )
                    return None
                source = await (
                    await conn.execute(
                        "SELECT * FROM kestri.messages WHERE id=%s AND chat_id=%s "
                        "AND direction='in' AND provenance='direct'",
                        (job["source_message_id"], chat_id),
                    )
                ).fetchone()
                if not source:
                    await conn.execute(
                        "UPDATE kestri.memory_jobs SET "
                        "status='cancelled',error_type='SourceUnavailable' "
                        "WHERE id=%s",
                        (job["id"],),
                    )
                    return None
                run_id = job["run_id"] or uuid4()
                token = uuid4()
                await conn.execute(
                    "INSERT INTO "
                    "kestri.runs(id,chat_id,message_id,request,status,kind,memory_epoch,started_at)"
                    " "
                    "VALUES (%s,%s,0,'Automatic memory "
                    "maintenance','running','memory_maintenance',%s,now()) "
                    "ON CONFLICT(id) DO UPDATE SET status='running',cancel_requested=false,"
                    "memory_epoch=EXCLUDED.memory_epoch,started_at=now(),finished_at=NULL,error_type=NULL",
                    (run_id, chat_id, state["memory_epoch"]),
                )
                # Keep interrupted reservations as unknown; do not refund them.
                await conn.execute(
                    "UPDATE kestri.usage SET state='unknown' WHERE run_id=%s AND state='reserved'",
                    (run_id,),
                )
                await conn.execute(
                    "UPDATE kestri.memory_jobs SET status='running',run_id=%s,lease_token=%s,"
                    "lease_until=now()+interval '120 seconds',attempts=attempts+1,"
                    "captured_revision=%s,captured_epoch=%s,updated_at=now() WHERE id=%s",
                    (run_id, token, state["memory_revision"], state["memory_epoch"], job["id"]),
                )
                job.update(
                    run_id=str(run_id),
                    lease_token=token,
                    attempts=job["attempts"] + 1,
                    captured_revision=state["memory_revision"],
                    captured_epoch=state["memory_epoch"],
                )
                return job

    async def snapshot(self, job: Row) -> ExtractionBatch:
        await self.ensure_active(job)
        state = await self.store.one(
            "SELECT * FROM kestri.conversations WHERE chat_id=%s", (job["chat_id"],)
        )
        assert state is not None
        cutoff = max(state["memory_activation_watermark"], state["automatic_history_floor"])
        rows = await self.store.all(
            "SELECT * FROM kestri.messages WHERE chat_id=%s AND id>%s AND id<=%s AND "
            "((direction='in' AND provenance='direct') OR (direction='out' AND "
            "provenance='context')) "
            "ORDER BY id DESC LIMIT 13",
            (job["chat_id"], cutoff, job["source_message_id"]),
        )
        fresh = next((r for r in rows if r["id"] == job["source_message_id"]), None)
        if fresh is None:
            raise PolicyDenied("MemorySourceUnavailable")
        if len(fresh["content"].encode("utf-8")) > 24000:
            raise PolicyDenied("MemorySourceOversized")
        selected = [fresh]
        size = len(fresh["content"].encode("utf-8"))
        for row in rows:
            if row["id"] == fresh["id"]:
                continue
            length = len(row["content"].encode("utf-8"))
            if size + length > 24000 or not row["content"]:
                continue
            selected.append(row)
            size += length
        memories = await self.store.all(
            "SELECT * FROM kestri.memories WHERE chat_id=%s AND status='active' AND task_id "
            "IS NULL "
            "AND (expires_at IS NULL OR expires_at>now()) AND (review_after IS NULL OR "
            "review_after>now()) "
            "AND content!='' ORDER BY updated_at DESC LIMIT 20",
            (job["chat_id"],),
        )
        existing = []
        size = 0
        for memory in memories:
            length = len(memory["content"].encode("utf-8"))
            if size + length > 12000:
                continue
            existing.append(
                ExistingMemory(
                    id=memory["id"],
                    chat_id=memory["chat_id"],
                    content=memory["content"],
                    category=memory["category"],
                    scope=memory["scope"],
                    task_id=memory["task_id"],
                    revision=memory["revision"],
                    last_source_message_id=memory["last_source_message_id"] or 1,
                    origin=memory["origin"],
                )
            )
            size += length
        return ExtractionBatch(
            chat_id=job["chat_id"],
            memory_revision=job["captured_revision"],
            memory_epoch=job["captured_epoch"],
            settings_generation=job["settings_generation"],
            enabled=True,
            activation_watermark=state["memory_activation_watermark"],
            automatic_history_floor=state["automatic_history_floor"],
            sources=tuple(
                MemorySource(
                    message_id=r["id"],
                    chat_id=r["chat_id"],
                    role="owner" if r["direction"] == "in" else "assistant",
                    provenance=r["provenance"],
                    text=r["content"],
                    created_at=r["created_at"],
                    fresh=r["id"] == fresh["id"],
                )
                for r in sorted(selected, key=lambda r: r["id"])
            ),
            existing=tuple(existing),
        )

    async def ensure_active(self, job: Row) -> None:
        row = await self.store.one(
            "SELECT 1 FROM kestri.memory_jobs j JOIN kestri.conversations c ON c.chat_id=j.chat_id "
            "JOIN kestri.runs r ON r.id=j.run_id JOIN kestri.messages m ON "
            "m.id=j.source_message_id "
            "WHERE j.id=%s AND j.lease_token=%s AND j.status='running' AND j.lease_until>now() "
            "AND r.status='running' AND NOT r.cancel_requested AND c.auto_memory_enabled "
            "AND c.memory_settings_generation=j.settings_generation AND "
            "c.memory_revision=j.captured_revision "
            "AND c.memory_epoch=j.captured_epoch AND "
            "m.id>GREATEST(c.memory_activation_watermark,c.automatic_history_floor)",
            (job["id"], job["lease_token"]),
        )
        if not row:
            raise PolicyDenied("MemoryJobChanged")

    async def publish(self, job: Row, result: ValidatedExtraction) -> int:
        # Caller cannot publish a result captured for another job/source or settings generation.
        if (
            result.batch.chat_id != job["chat_id"]
            or result.batch.memory_revision != job["captured_revision"]
            or result.batch.memory_epoch != job["captured_epoch"]
            or result.batch.settings_generation != job["settings_generation"]
            or [s.message_id for s in result.batch.sources if s.fresh] != [job["source_message_id"]]
        ):
            raise PolicyDenied("MemoryBatchMismatch")
        result = validate_proposal(
            result.batch, MemoryProposal(operations=list(result.operations)), self.store.redactor
        )
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                    (job["chat_id"],),
                )
                await self.ensure_active(job)
                counts = await (
                    await conn.execute(
                        "SELECT count(*) FILTER (WHERE status='active') AS active,"
                        "count(*) FILTER (WHERE status='candidate') AS candidate FROM "
                        "kestri.memories WHERE chat_id=%s",
                        (job["chat_id"],),
                    )
                ).fetchone()
                assert counts is not None
                active, candidate = counts["active"], counts["candidate"]
                replacements = False
                notice_lines: list[str] = []
                for op in result.operations:
                    status = "candidate" if op.action == "candidate" else "active"
                    if op.action == "reinforce":
                        memory_id = op.target_memory_id
                        await conn.execute(
                            "UPDATE kestri.memories SET "
                            "revision=revision+1,last_source_message_id=%s,updated_at=now() "
                            "WHERE id=%s",
                            (job["source_message_id"], memory_id),
                        )
                    else:
                        if op.action != "replace":
                            if status == "active":
                                active += 1
                            else:
                                candidate += 1
                        if (
                            active > self.settings.auto_memory_limit
                            or candidate > self.settings.memory_candidate_limit
                        ):
                            raise PolicyDenied("MemoryCapacityExceeded")
                        memory_id = uuid4()
                        source = next(
                            s
                            for s in result.batch.sources
                            if s.message_id == job["source_message_id"]
                        )
                        archived = await (
                            await conn.execute(
                                "SELECT telegram_id FROM kestri.messages WHERE id=%s",
                                (source.message_id,),
                            )
                        ).fetchone()
                        assert archived is not None
                        await conn.execute(
                            "INSERT INTO "
                            "kestri.memories(id,chat_id,content,scope,task_id,source_message_id,source_run_id,status,"
                            "supersedes,expires_at,category,origin,fact_key,valid_from,review_after,last_source_message_id)"
                            " "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                memory_id,
                                job["chat_id"],
                                op.content,
                                op.scope,
                                op.task_id,
                                archived["telegram_id"],
                                job["run_id"],
                                status,
                                op.target_memory_id,
                                op.expires_at,
                                op.category,
                                "auto_inferred" if status == "candidate" else "auto_direct",
                                op.fact_key,
                                op.valid_from,
                                op.review_after,
                                source.message_id,
                            ),
                        )
                        if op.action == "replace":
                            await conn.execute(
                                "UPDATE kestri.memories SET "
                                "status='superseded',revision=revision+1,updated_at=now() "
                                "WHERE id=%s",
                                (op.target_memory_id,),
                            )
                            replacements = True
                    if op.action in {"create", "replace"}:
                        verb = "更新" if op.action == "replace" else "记住"
                        notice_lines.append(f"{verb} {str(memory_id)[:8]}：{op.content[:120]}")
                    for ref in op.source_refs:
                        await conn.execute(
                            "INSERT INTO "
                            "kestri.memory_sources(memory_id,message_id,quote,start_offset,end_offset)"
                            " "
                            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                            (memory_id, ref.message_id, ref.quote, ref.start, ref.end),
                        )
                    await conn.execute(
                        "INSERT INTO kestri.memory_events(chat_id,memory_id,job_id,operation)"
                        " VALUES (%s,%s,%s,%s)",
                        (job["chat_id"], memory_id, job["id"], op.action),
                    )
                if result.operations:
                    await conn.execute(
                        "UPDATE kestri.conversations SET memory_revision=memory_revision+1,"
                        "memory_epoch=memory_epoch+%s,thread_id=CASE WHEN %s THEN NULL ELSE "
                        "thread_id END WHERE chat_id=%s",
                        (int(replacements), replacements, job["chat_id"]),
                    )
                await conn.execute(
                    "UPDATE kestri.memory_jobs SET "
                    "status='succeeded',lease_until=NULL,updated_at=now(),error_type=NULL "
                    "WHERE id=%s",
                    (job["id"],),
                )
                await conn.execute(
                    "UPDATE kestri.runs SET "
                    "status='completed',finished_at=now(),result='Memory extraction "
                    "committed' WHERE id=%s",
                    (job["run_id"],),
                )
                if notice_lines:
                    notice = "记忆已更新：\n" + "\n".join(notice_lines)
                    notice += "\n不准确时可用 /correct ID 完整内容；不再保留可用 /forget ID。"
                    await conn.execute(
                        """
                        INSERT INTO kestri.outbox (id, chat_id, run_id, content)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (uuid4(), job["chat_id"], job["run_id"], self.store.redactor.text(notice)),
                    )
                return len(result.operations)

    async def fail(self, job: Row, error_type: str, retry: bool = False) -> None:
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                    (job["chat_id"],),
                )
                current = await (
                    await conn.execute(
                        "SELECT * FROM kestri.memory_jobs WHERE id=%s AND lease_token=%s AND "
                        "status='running' FOR UPDATE",
                        (job["id"], job["lease_token"]),
                    )
                ).fetchone()
                if not current:
                    return
                retry = retry and current["attempts"] < 3
                await conn.execute(
                    "UPDATE kestri.memory_jobs SET "
                    "status=%s,available_at=now()+make_interval(secs=>%s),"
                    "lease_until=NULL,error_type=%s,updated_at=now() WHERE id=%s",
                    (
                        "retry_wait" if retry else "failed",
                        5 if current["attempts"] == 1 else 30,
                        error_type,
                        job["id"],
                    ),
                )
                await conn.execute(
                    "UPDATE kestri.runs SET status='failed',finished_at=now(),error_type=%s "
                    "WHERE id=%s",
                    (error_type, job["run_id"]),
                )
                await conn.execute(
                    "UPDATE kestri.usage SET state='unknown' WHERE run_id=%s AND state='reserved'",
                    (job["run_id"],),
                )
