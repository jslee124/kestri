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
    conn: Any, chat_id: int, text: str, *, embedding_space: str | None = None
) -> str:
    from kestri.memory.service import display, listing

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
            "memory_revision=memory_revision+1,memory_epoch=memory_epoch+1,thread_id=NULL "
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
            "已开启语义召回：有效记忆、合格历史片段与查询将发送到北京 DashScope，"
            "事实候选筛选使用 DeepSeek。"
            "只重建有效事实索引，不扫描旧聊天；/memory semantic off 可关闭。"
            if semantic and enabled
            else "已关闭语义召回，保留本地索引并回到词项召回。"
            if semantic
            else "已开启记忆使用。"
            if enabled
            else "已关闭记忆使用，停止记忆注入和索引调用；"
            "自动提取开关独立，/memory auto off 可关闭学习。"
        ) + "前台上下文已重置。"
    if args == ["changes"]:
        events = await (
            await conn.execute(
                "SELECT memory_id,operation,created_at FROM kestri.memory_events "
                "WHERE chat_id=%s ORDER BY id DESC LIMIT 20",
                (chat_id,),
            )
        ).fetchall()
        jobs = await (
            await conn.execute(
                "SELECT status,count(*) AS n FROM kestri.memory_jobs WHERE chat_id=%s "
                "GROUP BY status ORDER BY status",
                (chat_id,),
            )
        ).fetchall()
        errors = await (
            await conn.execute(
                "SELECT source_message_id,error_type FROM kestri.memory_jobs "
                "WHERE chat_id=%s AND status='failed' ORDER BY updated_at DESC LIMIT 3",
                (chat_id,),
            )
        ).fetchall()
        indexing = await (
            await conn.execute(
                "SELECT status,count(*) AS n FROM kestri.memory_index_jobs WHERE chat_id=%s "
                "GROUP BY status ORDER BY status",
                (chat_id,),
            )
        ).fetchall()
        index_errors = await (
            await conn.execute(
                "SELECT error_type FROM kestri.memory_index_jobs WHERE chat_id=%s "
                "AND status='failed' "
                "ORDER BY updated_at DESC LIMIT 3",
                (chat_id,),
            )
        ).fetchall()
        return (
            "向量作业："
            + ("；".join(f"{r['status']} {r['n']}" for r in indexing) or "无")
            + "\n向量失败："
            + ("；".join(r["error_type"] for r in index_errors) or "无")
            + "\n"
            + "后台作业："
            + ("；".join(f"{r['status']} {r['n']}" for r in jobs) or "无")
            + "\n最近变更：\n"
            + (
                "\n".join(
                    f"{str(r['memory_id'])[:8]} · {r['operation']} · {r['created_at'].isoformat()}"
                    for r in events
                )
                or "无"
            )
            + "\n失败类别：\n"
            + (
                "\n".join(f"来源记录 {r['source_message_id']} · {r['error_type']}" for r in errors)
                or "无"
            )
        )
    if args == ["pending"]:
        rows = await (
            await conn.execute(
                "SELECT * FROM kestri.memories WHERE chat_id=%s AND status='candidate' "
                "ORDER BY updated_at DESC LIMIT 100",
                (chat_id,),
            )
        ).fetchall()
        return "\n\n".join(display(row) for row in rows) or "暂无候选推断；候选不会进入回答。"
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
            "memory_epoch=memory_epoch+1,thread_id=NULL,"
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
            "已开启自动记忆：只处理之后的直接聊天，发送到 DeepSeek 整理；"
            "旧历史不会扫描，前台上下文已重置。"
            "开启后聊天也可按需发送到 DeepSeek，用于回答历史问题。"
            "用 /memory 查看、/memory pending 查看候选、/memory changes 查看后台作业、"
            "/memory auto off 关闭。"
            if enabled
            else "已关闭自动记忆，在途提案不能提交，历史工具暂停，"
            "前台上下文已重置；已有记忆仍可使用。"
        )
    if args:
        return "格式：/memory；/memory pending；/memory changes；/memory auto|use|semantic on|off。"
    state = await (
        await conn.execute(
            "SELECT * FROM kestri.conversations WHERE chat_id=%s",
            (chat_id,),
        )
    ).fetchone()
    return (
        "自动记忆："
        + ("开启" if state and state["auto_memory_enabled"] else "关闭")
        + "；使用："
        + ("开启" if state and state["memory_use_enabled"] else "关闭")
        + "；语义召回："
        + ("开启" if state and state["memory_semantic_enabled"] else "关闭")
        + "\n\n"
        + await listing(conn, chat_id)
    )


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
                # No unsolicited Telegram notice; /memory exposes content and sources.
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
