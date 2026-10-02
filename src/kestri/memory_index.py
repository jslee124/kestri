"""Persistent leased indexing. Source versions/settings gate billing and vector publication."""

import asyncio
from uuid import uuid4

from kestri.budget import Budget, RunControl, micro_usd
from kestri.embedding import EmbeddingClient
from kestri.errors import BudgetExceeded, PolicyDenied, ProviderFailure
from kestri.memory_embedding import charged_embedding, embedding_space, vector_literal
from kestri.settings import ResearchSettings
from kestri.store import Row, Store


class IndexControl(RunControl):
    def __init__(self, worker: MemoryIndexWorker, job: Row) -> None:
        super().__init__(worker.store, str(job["run_id"]))
        self.worker = worker
        self.job = job

    async def ensure_active(self) -> None:
        await self.worker.ensure_active(self.job)
        await super().ensure_active()


class IndexBudget(Budget):
    async def reserve(self, kind: str, amount: int) -> str:
        await self.control.ensure_active()
        assert isinstance(self.control, IndexControl)
        return await self.control.store.reserve(
            self.control.run_id,
            "memory_index",
            amount,
            micro_usd(self.settings.monthly_budget_usd),
            micro_usd(self.settings.memory_maintenance_budget_usd),
            maintenance_monthly=micro_usd(self.settings.memory_maintenance_monthly_usd),
            index_job=(str(self.control.job["id"]), str(self.control.job["lease_token"])),
        )


class MemoryIndexWorker:
    def __init__(self, store: Store, settings: ResearchSettings, client: EmbeddingClient) -> None:
        self.store = store
        self.settings = settings
        self.client = client
        self.space = embedding_space(client.settings)

    async def ensure_active(self, job: Row) -> None:
        row = await self.store.one(
            "SELECT 1 FROM kestri.memory_index_jobs j JOIN kestri.conversations c "
            "ON c.chat_id=j.chat_id JOIN kestri.memories m ON m.id=j.memory_id "
            "JOIN kestri.runs r ON r.id=j.run_id WHERE j.id=%s AND j.lease_token=%s "
            "AND j.status='running' AND j.lease_until>now() AND r.status='running' "
            "AND NOT r.cancel_requested AND c.memory_use_enabled AND c.memory_semantic_enabled "
            "AND c.memory_retrieval_generation=j.generation AND "
            "c.memory_embedding_space=j.embedding_space "
            "AND j.embedding_space=%s AND m.status='active' AND m.origin!='auto_inferred' "
            "AND m.revision=j.revision "
            "AND md5(m.content)=j.content_hash AND (m.expires_at IS NULL OR m.expires_at>now()) "
            "AND (m.review_after IS NULL OR m.review_after>now())",
            (job["id"], job["lease_token"], self.space),
        )
        if not row:
            raise PolicyDenied("MemoryIndexChanged")

    async def claim(self, chat_id: int) -> Row | None:
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                state = await (
                    await conn.execute(
                        "SELECT * FROM kestri.conversations WHERE chat_id=%s FOR UPDATE", (chat_id,)
                    )
                ).fetchone()
                if (
                    not state
                    or not state["memory_use_enabled"]
                    or not state["memory_semantic_enabled"]
                    or state["memory_embedding_space"] != self.space
                ):
                    return None
                if await (
                    await conn.execute(
                        "SELECT 1 FROM kestri.runs WHERE chat_id=%s "
                        "AND kind NOT IN ('background','memory_maintenance') "
                        "AND status IN ('queued','running') LIMIT 1",
                        (chat_id,),
                    )
                ).fetchone():
                    return None
                job = await (
                    await conn.execute(
                        "SELECT *,available_at<=now() AS ready,"
                        "lease_until>now() AS leased FROM kestri.memory_index_jobs WHERE"
                        " chat_id=%s "
                        "AND status IN ('queued','running','retry_wait') ORDER BY created_at,id "
                        "LIMIT 1 FOR UPDATE",
                        (chat_id,),
                    )
                ).fetchone()
                if not job or not job["ready"] or (job["status"] == "running" and job["leased"]):
                    return None
                memory = await (
                    await conn.execute(
                        "SELECT * FROM kestri.memories WHERE id=%s "
                        "AND status='active' AND origin!='auto_inferred' AND revision=%s "
                        "AND md5(content)=%s "
                        "AND (expires_at IS NULL OR expires_at>now()) "
                        "AND (review_after IS NULL OR review_after>now())",
                        (job["memory_id"], job["revision"], job["content_hash"]),
                    )
                ).fetchone()
                if (
                    not memory
                    or job["generation"] != state["memory_retrieval_generation"]
                    or job["embedding_space"] != self.space
                    or job["attempts"] >= 3
                ):
                    await conn.execute(
                        "UPDATE kestri.memory_index_jobs SET status='cancelled',"
                        "lease_until=NULL,error_type='IndexIneligible',updated_at=now() "
                        "WHERE id=%s",
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
                run_id, token = job["run_id"] or uuid4(), uuid4()
                await conn.execute(
                    "INSERT INTO kestri.runs(id,chat_id,message_id,request,status,kind,"
                    "memory_epoch,started_at) VALUES (%s,%s,0,'Memory vector indexing','running',"
                    "'memory_maintenance',%s,now()) ON CONFLICT(id) DO UPDATE SET status='running',"
                    "cancel_requested=false,started_at=now(),finished_at=NULL,error_type=NULL,"
                    "memory_epoch=EXCLUDED.memory_epoch",
                    (run_id, chat_id, state["memory_epoch"]),
                )
                await conn.execute(
                    "UPDATE kestri.usage SET state='unknown' WHERE run_id=%s AND state='reserved'",
                    (run_id,),
                )
                await conn.execute(
                    "UPDATE kestri.memory_index_jobs SET status='running',run_id=%s,"
                    "lease_token=%s,lease_until=now()+interval '120 seconds',attempts=attempts+1,"
                    "updated_at=now() WHERE id=%s",
                    (run_id, token, job["id"]),
                )
                return {
                    **job,
                    "run_id": str(run_id),
                    "lease_token": token,
                    "attempts": job["attempts"] + 1,
                    "content": memory["content"],
                }

    async def publish(self, job: Row, vector: tuple[float, ...]) -> None:
        from math import hypot, isfinite

        if len(vector) != 1024 or not all(isfinite(v) for v in vector) or hypot(*vector) == 0:
            raise PolicyDenied("InvalidIndexVector")
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                    (job["chat_id"],),
                )
                await self.ensure_active(job)
                await conn.execute(
                    "INSERT INTO kestri.memory_embeddings(memory_id,revision,content_hash,"
                    "embedding_space,embedding) VALUES (%s,%s,%s,%s,%s::public.vector) "
                    "ON CONFLICT(memory_id,embedding_space) DO UPDATE SET "
                    "revision=EXCLUDED.revision,"
                    "content_hash=EXCLUDED.content_hash,embedding=EXCLUDED.embedding,created_at=now()",
                    (
                        job["memory_id"],
                        job["revision"],
                        job["content_hash"],
                        self.space,
                        vector_literal(vector),
                    ),
                )
                await conn.execute(
                    "UPDATE kestri.memory_index_jobs SET status='succeeded',lease_until=NULL,"
                    "error_type=NULL,updated_at=now() WHERE id=%s",
                    (job["id"],),
                )
                await conn.execute(
                    "UPDATE kestri.runs SET status='completed',finished_at=now(),"
                    "result='Vector index published' WHERE id=%s",
                    (job["run_id"],),
                )

    async def fail(self, job: Row, category: str, *, retry: bool = False) -> None:
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                    (job["chat_id"],),
                )
                current = await (
                    await conn.execute(
                        "SELECT attempts FROM kestri.memory_index_jobs "
                        "WHERE id=%s AND lease_token=%s AND status='running' FOR UPDATE",
                        (job["id"], job["lease_token"]),
                    )
                ).fetchone()
                if not current:
                    return
                retry = retry and current["attempts"] < 3
                await conn.execute(
                    "UPDATE kestri.memory_index_jobs SET status=%s,error_type=%s,"
                    "lease_until=NULL,available_at=now()+make_interval(secs=>%s),updat"
                    "ed_at=now() WHERE id=%s",
                    (
                        "retry_wait" if retry else "failed",
                        category,
                        5 if current["attempts"] == 1 else 30,
                        job["id"],
                    ),
                )
                await conn.execute(
                    "UPDATE kestri.runs SET "
                    "status='failed',error_type=%s,finished_at=now() WHERE id=%s",
                    (category, job["run_id"]),
                )
                await conn.execute(
                    "UPDATE kestri.usage SET state='unknown' WHERE run_id=%s AND state='reserved'",
                    (job["run_id"],),
                )

    async def work_once(self, chat_id: int) -> bool:
        job = await self.claim(chat_id)
        if job is None:
            return False
        try:
            result = await charged_embedding(
                self.client,
                [job["content"]],
                IndexBudget(self.settings, IndexControl(self, job)),
                "memory_index",
            )
            await self.publish(job, result.vectors[0])
        except asyncio.CancelledError:
            await self.fail(job, "WorkerInterrupted", retry=True)
            raise
        except TimeoutError:
            await self.fail(job, "EmbeddingTransient", retry=True)
        except ProviderFailure as error:
            transient = str(error) in {
                "EmbeddingTransportFailure",
                "HTTP_429",
                "HTTP_500",
                "HTTP_502",
                "HTTP_503",
                "HTTP_504",
            }
            await self.fail(
                job, "EmbeddingTransient" if transient else "EmbeddingRejected", retry=transient
            )
        except BudgetExceeded:
            await self.fail(job, "MaintenanceBudgetExceeded")
        except Exception:
            await self.fail(job, "IndexRejected")
        return True
