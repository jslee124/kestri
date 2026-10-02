"""Durable background history indexing, with source-version leases and shared caps."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from psycopg import AsyncConnection

from kestri.agent.budget import Budget, RunControl, micro_usd
from kestri.errors import BudgetExceeded, PolicyDenied, ProviderFailure
from kestri.history.retriever import HistoryRetriever
from kestri.history.semantic import RECIPE, HistorySemantic, encode_turn, history_space
from kestri.integrations.embedding import EmbeddingClient
from kestri.memory.embedding import charged_embedding, embedding_space
from kestri.settings import ResearchSettings
from kestri.storage.store import Row, Store


class HistoryJobControl(RunControl):
    def __init__(self, worker: HistoryIndexWorker, job: Row) -> None:
        super().__init__(worker.store, str(job["run_id"]))
        self.worker, self.job = worker, job

    async def ensure_active(self) -> None:
        await self.worker.ensure_active(self.job)
        await super().ensure_active()


class HistoryIndexBudget(Budget):
    async def reserve(self, kind: str, amount: int) -> str:
        await self.control.ensure_active()
        assert isinstance(self.control, HistoryJobControl)
        job = self.control.job
        return await self.control.store.reserve(
            self.control.run_id,
            "history_index",
            amount,
            micro_usd(self.settings.monthly_budget_usd),
            micro_usd(self.settings.memory_maintenance_budget_usd),
            maintenance_monthly=micro_usd(self.settings.memory_maintenance_monthly_usd),
            history_job=(str(job["id"]), str(job["lease_token"]), job["source_revision"]),
        )


class HistoryIndexWorker:
    def __init__(self, store: Store, settings: ResearchSettings, client: EmbeddingClient) -> None:
        self.store, self.settings, self.client = store, settings, client
        self.space = embedding_space(client.settings)

    async def ensure_active(self, job: Row, conn: AsyncConnection[Row] | None = None) -> None:
        sql = (
            "SELECT 1 FROM kestri.history_index_jobs j JOIN kestri.conversations c ON "
            "c.chat_id=j.chat_id JOIN kestri.messages m ON m.id=j.owner_message_id "
            "JOIN kestri.runs s ON s.id=m.run_id JOIN kestri.runs r ON r.id=j.run_id "
            "WHERE j.id=%s AND j.lease_token=%s AND j.source_revision=%s "
            "AND j.status='running' AND j.lease_until>now() AND r.status='running' "
            "AND NOT r.cancel_requested AND c.auto_memory_enabled AND c.memory_use_enabled "
            "AND c.memory_semantic_enabled AND c.memory_settings_generation=j.settings_generation "
            "AND c.memory_retrieval_generation=j.retrieval_generation "
            "AND c.memory_embedding_space=j.embedding_space AND j.embedding_space=%s "
            "AND m.id>GREATEST(c.memory_activation_watermark,c.automatic_history_floor) "
            "AND m.direction='in' AND m.provenance='direct' AND s.kind='foreground' "
            "AND NOT s.history_expired AND (m.task_id IS NULL OR EXISTS(SELECT 1 FROM "
            "kestri.tasks WHERE id=m.task_id AND status!='deleted'))"
        )
        params = (job["id"], job["lease_token"], job["source_revision"], self.space)
        row = (
            await (await conn.execute(sql + " FOR UPDATE OF j", params)).fetchone()
            if conn
            else await self.store.one(sql, params)
        )
        if not row:
            raise PolicyDenied("HistoryJobChanged")

    def retriever(self, job: Row, state: Row, task_id: object) -> HistoryRetriever:
        run = {
            "id": job.get("run_id") or str(uuid4()),
            "chat_id": job["chat_id"],
            "created_at": datetime.now(UTC),
            "task_id": task_id,
            "memory_epoch": state["memory_epoch"],
            "kind": "foreground",
        }
        return HistoryRetriever(
            self.store, Budget(self.settings, RunControl(self.store, str(run["id"]))), run
        )

    async def claim(self, chat_id: int) -> Row | None:
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                state = await (
                    await conn.execute(
                        "SELECT * FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                        (chat_id,),
                    )
                ).fetchone()
                if (
                    not state
                    or not all(
                        state[k]
                        for k in (
                            "auto_memory_enabled",
                            "memory_use_enabled",
                            "memory_semantic_enabled",
                        )
                    )
                    or state["memory_embedding_space"] != self.space
                ):
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
                        "FROM kestri.history_index_jobs WHERE chat_id=%s "
                        "AND status IN ('queued','running','retry_wait') ORDER BY "
                        "created_at,id LIMIT 1 FOR UPDATE",
                        (chat_id,),
                    )
                ).fetchone()
                if not job or not job["ready"] or (job["status"] == "running" and job["leased"]):
                    return None
                owner = await (
                    await conn.execute(
                        "SELECT task_id FROM kestri.messages WHERE id=%s",
                        (job["owner_message_id"],),
                    )
                ).fetchone()
                lookup = self.retriever(job, state, owner["task_id"] if owner else None)
                rows = (
                    await lookup.turns(state, None, None, job["owner_message_id"], conn=conn)
                    if owner
                    else []
                )
                if (
                    not owner
                    or not rows
                    or job["settings_generation"] != state["memory_settings_generation"]
                    or job["retrieval_generation"] != state["memory_retrieval_generation"]
                    or job["embedding_space"] != self.space
                    or job["attempts"] >= 3
                    or len(encode_turn(rows[0]).encode()) > 8192
                ):
                    await conn.execute(
                        "UPDATE kestri.history_index_jobs SET "
                        "status='cancelled',lease_until=NULL,error_type='HistoryIneligible'"
                        ",updated_at=now() WHERE id=%s",
                        (job["id"],),
                    )
                    if job["run_id"]:
                        await conn.execute(
                            "UPDATE kestri.runs SET "
                            "status='cancelled',cancel_requested=true,finished_at=now() "
                            "WHERE id=%s",
                            (job["run_id"],),
                        )
                        await conn.execute(
                            "UPDATE kestri.usage SET state='unknown' WHERE run_id=%s AND "
                            "state='reserved'",
                            (job["run_id"],),
                        )
                    return None
                source = rows[0]
                cached = await (
                    await conn.execute(
                        "SELECT 1 FROM kestri.history_embeddings WHERE owner_message_id=%s "
                        "AND source_hash=%s AND embedding_space=%s AND settings_generation=%s "
                        "AND retrieval_generation=%s",
                        (
                            job["owner_message_id"],
                            source["id"],
                            history_space(self.client),
                            job["settings_generation"],
                            job["retrieval_generation"],
                        ),
                    )
                ).fetchone()
                if cached:
                    await conn.execute(
                        "UPDATE kestri.history_index_jobs SET "
                        "status='succeeded',source_hash=%s,lease_until=NULL,error_type=NULL"
                        ",updated_at=now() WHERE id=%s",
                        (source["id"], job["id"]),
                    )
                    if job["run_id"]:
                        await conn.execute(
                            "UPDATE kestri.usage SET state='unknown' WHERE run_id=%s AND "
                            "state='reserved'",
                            (job["run_id"],),
                        )
                        await conn.execute(
                            "UPDATE kestri.runs SET "
                            "status='completed',finished_at=now(),result='Existing history "
                            "vector reused' WHERE id=%s",
                            (job["run_id"],),
                        )
                    return None
                run_id, token = job["run_id"] or uuid4(), uuid4()
                await conn.execute(
                    "INSERT INTO "
                    "kestri.runs(id,chat_id,message_id,request,status,kind,memory_epoch,sta"
                    "rted_at) "
                    "VALUES (%s,%s,0,'History vector "
                    "indexing','running','memory_maintenance',%s,now()) "
                    "ON CONFLICT(id) DO UPDATE SET "
                    "status='running',cancel_requested=false,started_at=now(),"
                    "finished_at=NULL,error_type=NULL,memory_epoch=EXCLUDED.memory_epoch",
                    (run_id, chat_id, state["memory_epoch"]),
                )
                await conn.execute(
                    "UPDATE kestri.usage SET state='unknown' WHERE run_id=%s AND state='reserved'",
                    (run_id,),
                )
                await conn.execute(
                    "UPDATE kestri.history_index_jobs SET "
                    "status='running',source_hash=%s,run_id=%s,lease_token=%s,"
                    "lease_until=now()+interval '120 "
                    "seconds',attempts=attempts+1,updated_at=now() WHERE id=%s",
                    (source["id"], run_id, token, job["id"]),
                )
                return {
                    **job,
                    "run_id": str(run_id),
                    "lease_token": token,
                    "attempts": job["attempts"] + 1,
                    "source": source,
                    "state": state,
                    "task_id": owner["task_id"],
                    "source_hash": source["id"],
                }

    async def publish(self, job: Row, vector: tuple[float, ...]) -> None:
        async def guard(conn: AsyncConnection[Row]) -> None:
            await self.ensure_active(job, conn)

        async def complete(conn: AsyncConnection[Row]) -> None:
            await conn.execute(
                "UPDATE kestri.history_index_jobs SET "
                "status='succeeded',lease_until=NULL,error_type=NULL,updated_at=now() WHERE id=%s",
                (job["id"],),
            )
            await conn.execute(
                "UPDATE kestri.runs SET "
                "status='completed',finished_at=now(),result='History vector published' "
                "WHERE id=%s",
                (job["run_id"],),
            )

        semantic = HistorySemantic(self.retriever(job, job["state"], job["task_id"]), self.client)
        await semantic.publish(
            job["state"], [job["source"]], [vector], guard=guard, complete=complete
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
                        "SELECT attempts FROM kestri.history_index_jobs WHERE id=%s AND "
                        "lease_token=%s "
                        "AND source_revision=%s AND status='running' FOR UPDATE",
                        (job["id"], job["lease_token"], job["source_revision"]),
                    )
                ).fetchone()
                if not current:
                    return
                retry = retry and current["attempts"] < 3
                await conn.execute(
                    "UPDATE kestri.history_index_jobs SET status=%s,error_type=%s,lease_until=NULL,"
                    "available_at=now()+make_interval(secs=>%s),updated_at=now() WHERE id=%s",
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
                [encode_turn(job["source"])],
                HistoryIndexBudget(self.settings, HistoryJobControl(self, job)),
                "history_index",
                recipe=RECIPE,
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
        except PolicyDenied:
            await self.fail(job, "HistoryChanged", retry=True)
        except Exception:
            await self.fail(job, "HistoryIndexRejected")
        return True
