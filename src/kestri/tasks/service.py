"""Stored owner agreements, transactional controls, and coalescing local scheduling."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, field_validator

from kestri.settings import ResearchSettings
from kestri.storage.store import Row, Store
from kestri.tasks.intent import TaskAction
from kestri.tasks.schedule import (
    latest_occurrence,
    next_occurrence,
)

if TYPE_CHECKING:
    from kestri.tasks.dialogue import Continuation


class TaskPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["create", "update", "pause", "resume", "delete", "list", "clarify"]
    target: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, max_length=100)
    instructions: str | None = Field(default=None, max_length=4000)
    local_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: str | None = Field(default=None, max_length=100)
    weekdays: list[int] | None = Field(default=None, min_length=1, max_length=7)
    clarification: str | None = Field(default=None, max_length=500)

    @field_validator("weekdays")
    @classmethod
    def valid_days(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and (
            len(set(value)) != len(value) or any(d < 0 or d > 6 for d in value)
        ):
            raise ValueError("InvalidWeekdays")
        return sorted(value) if value is not None else None

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value: str | None) -> str | None:
        if value is not None:
            ZoneInfo(value)
        return value


async def list_tasks(conn: Any, chat_id: int) -> str:
    from kestri.tasks.presentation import view

    return await view(conn, chat_id)


class TaskService:
    def __init__(self, store: Store, settings: ResearchSettings) -> None:
        self.store = store
        self.settings = settings

    async def apply(
        self,
        run: Row,
        plan: TaskPlan,
        intent: TaskAction,
        now: datetime | None = None,
        *,
        continuation: Continuation | None = None,
    ) -> str:
        from kestri.tasks.controls import apply_control

        return await apply_control(
            self.store,
            self.settings,
            run,
            plan,
            intent,
            now or datetime.now(UTC),
            continuation,
        )

    async def tick(self, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        created = 0
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                # Shared ordering with owner controls and background claim: conversation, task, run.
                await conn.execute(
                    "SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                    (self.settings.telegram_owner_id,),
                )
                await conn.execute(
                    """
                    UPDATE kestri.runs AS r
                    SET status = 'cancelled', cancel_requested = true,
                        finished_at = %s, error_type = 'CatchUpExpired'
                    FROM kestri.tasks AS t
                    WHERE r.task_id = t.id AND r.status = 'queued'
                      AND r.kind = 'background'
                      AND r.scheduled_for + make_interval(secs => t.catch_up_seconds) < %s
                    """,
                    (now, now),
                )
                tasks = await (
                    await conn.execute(
                        """
                        SELECT * FROM kestri.tasks
                        WHERE chat_id = %s AND status = 'active' AND next_due <= %s
                        ORDER BY next_due
                        FOR UPDATE
                        """,
                        (self.settings.telegram_owner_id, now),
                    )
                ).fetchall()
                count = await (
                    await conn.execute(
                        """
                        SELECT count(*) AS n FROM kestri.runs
                        WHERE kind = 'background' AND status IN ('queued', 'running')
                        """
                    )
                ).fetchone()
                remaining = self.settings.background_queue_limit - (count["n"] if count else 0)
                for task in tasks:
                    latest = latest_occurrence(
                        now,
                        task["local_time"],
                        task["timezone"],
                        task["weekdays"],
                    )
                    if latest < task["next_due"]:
                        continue
                    age = (now - latest).total_seconds()
                    active = await (
                        await conn.execute(
                            """
                            SELECT id FROM kestri.runs
                            WHERE task_id = %s AND kind = 'background'
                              AND status IN ('queued', 'running')
                            """,
                            (task["id"],),
                        )
                    ).fetchone()
                    eligible = age <= task["catch_up_seconds"]
                    if eligible and not active and remaining <= 0:
                        continue  # Keep due until capacity is available or the window expires.
                    if eligible and not active:
                        request = (
                            f"Stored owner agreement: {task['instructions']}\n"
                            f"Scheduled briefing time (UTC): {latest.isoformat()}\n"
                            f"Task timezone: {task['timezone']}. "
                            "Produce the agreed briefing only."
                        )
                        await conn.execute(
                            """
                            INSERT INTO kestri.runs (
                                id, chat_id, message_id, request, status, kind,
                                task_id, task_revision, scheduled_for
                            )
                            VALUES (%s, %s, 0, %s, 'queued', 'background', %s, %s, %s)
                            ON CONFLICT (task_id, scheduled_for) DO NOTHING
                            """,
                            (
                                uuid4(),
                                task["chat_id"],
                                request,
                                task["id"],
                                task["revision"],
                                latest,
                            ),
                        )
                        created += 1
                        remaining -= 1
                    await conn.execute(
                        "UPDATE kestri.tasks SET next_due=%s WHERE id=%s",
                        (
                            next_occurrence(
                                now,
                                task["local_time"],
                                task["timezone"],
                                task["weekdays"],
                            ),
                            task["id"],
                        ),
                    )
                    await conn.execute(
                        "INSERT INTO kestri.events(kind,metadata) VALUES ('schedule_decision',%s)",
                        (
                            Jsonb(
                                {
                                    "task_id": str(task["id"]),
                                    "scheduled_for": latest.isoformat(),
                                    "decision": "queued"
                                    if eligible and not active
                                    else "coalesced_busy"
                                    if active
                                    else "skipped_expired",
                                }
                            ),
                        ),
                    )
        return created
