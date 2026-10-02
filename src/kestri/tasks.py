"""Stored owner agreements, transactional controls, and coalescing local scheduling."""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, field_validator

from kestri.errors import PolicyDenied
from kestri.schedule import latest_occurrence, next_occurrence, requested_time, requested_weekdays
from kestri.settings import ResearchSettings
from kestri.store import Row, Store
from kestri.task_intent import TaskAction, task_intent


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


def agreement(task: Row) -> str:
    days = (
        "每天"
        if len(task["weekdays"]) == 7
        else "每周 " + ",".join(str(d + 1) for d in task["weekdays"])
    )
    return (
        f"任务 {str(task['id'])[:8]} · {task['title']} · {task['status']} · v{task['revision']}\n"
        f"时间：{days} {task['local_time']}，时区 {task['timezone']}\n"
        f"内容：{task['instructions']}\n"
        f"错过执行：{task['catch_up_seconds'] / 3600:g} 小时内合并补跑一次，超出则跳过。\n"
        f"下次计划（UTC）：{task['next_due'].isoformat()}\n"
        "暂停/删除阻止后续启动，已开始的执行继续；停止执行需用 /stop 执行ID。"
        + (
            "\n备份恢复的任务已暂停；核对约定后明确恢复才会重新授权。"
            if task.get("restored")
            else ""
        )
    )


async def list_tasks(conn: Any, chat_id: int) -> str:
    rows = await (
        await conn.execute(
            "SELECT * FROM kestri.tasks WHERE chat_id=%s AND status!='deleted' ORDER BY created_at",
            (chat_id,),
        )
    ).fetchall()
    return (
        "\n\n".join(agreement(row) for row in rows)
        or "暂无持续任务。用自然语言指定每日/每周的时间、时区和简报内容。"
    )


class TaskService:
    def __init__(self, store: Store, settings: ResearchSettings) -> None:
        self.store, self.settings = store, settings

    async def apply(
        self, run: Row, plan: TaskPlan, intent: TaskAction, now: datetime | None = None
    ) -> str:
        now = now or datetime.now(UTC)
        text = run["request"]
        # The caller cannot manufacture a capability from model output or retrieved material.
        if (
            run["kind"] != "task_control"
            or task_intent(text, task_reference=run["reply_to"] is not None) != intent
        ):
            raise PolicyDenied("TaskAuthorizationUnavailable")
        if plan.action not in {intent, "clarify"}:
            raise PolicyDenied("TaskActionMismatch")
        async with self.store.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT chat_id FROM kestri.conversations WHERE chat_id=%s FOR UPDATE",
                    (run["chat_id"],),
                )
                current = await (
                    await conn.execute(
                        "SELECT * FROM kestri.runs WHERE id=%s FOR UPDATE", (run["id"],)
                    )
                ).fetchone()
                if not current or current["status"] != "running" or current["cancel_requested"]:
                    raise PolicyDenied("RunInactive")
                prior = await (
                    await conn.execute(
                        "SELECT result FROM kestri.task_changes WHERE run_id=%s", (run["id"],)
                    )
                ).fetchone()
                if prior:
                    return str(prior["result"])
                task: Row | None = None
                notice = ""
                if plan.action == "clarify":
                    notice = "请补充后重新发送完整任务指令：" + (
                        plan.clarification or "明确时间、时区、内容和目标任务。"
                    )
                elif intent == "list":
                    notice = await list_tasks(conn, run["chat_id"])
                elif intent == "create":
                    zone = plan.timezone or self.settings.owner_timezone
                    if (
                        not zone
                        or not plan.local_time
                        or not plan.weekdays
                        or not plan.instructions
                        or plan.local_time != requested_time(text)
                        or plan.weekdays != requested_weekdays(text)
                    ):
                        notice = (
                            "尚未创建任务。请补充每日/每周时间、IANA 时区"
                            "（如 Asia/Shanghai）及内容，然后重新发送完整指令。"
                        )
                    elif (
                        plan.timezone
                        and plan.timezone not in text
                        and plan.timezone != self.settings.owner_timezone
                    ):
                        notice = "尚未创建任务。请在请求中明确 IANA 时区，或配置主人时区。"
                    else:
                        if plan.instructions not in text:
                            raise PolicyDenied("InstructionsMustComeFromOwner")
                        count = await (
                            await conn.execute(
                                (
                                    "SELECT count(*) AS n FROM kestri.tasks WHERE chat_id=%s AND "
                                    "status!='deleted'"
                                ),
                                (run["chat_id"],),
                            )
                        ).fetchone()
                        if count and count["n"] >= self.settings.task_limit:
                            notice = "持续任务数量已达上限；未创建任务。"
                        else:
                            task = await (
                                await conn.execute(
                                    (
                                        "INSERT INTO "
                                        "kestri.tasks(id,chat_id,title,instructions,timezone,local_time,weekdays,catch_up_seconds,status,next_due,authorized_run_id)"
                                        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'active',%s,%s) "
                                        "RETURNING *"
                                    ),
                                    (
                                        uuid4(),
                                        run["chat_id"],
                                        plan.title or "个人简报",
                                        plan.instructions,
                                        zone,
                                        plan.local_time,
                                        plan.weekdays,
                                        21600,
                                        next_occurrence(now, plan.local_time, zone, plan.weekdays),
                                        run["id"],
                                    ),
                                )
                            ).fetchone()
                else:
                    candidates = await (
                        await conn.execute(
                            (
                                "SELECT * FROM kestri.tasks WHERE chat_id=%s AND "
                                "status!='deleted' ORDER BY created_at FOR UPDATE"
                            ),
                            (run["chat_id"],),
                        )
                    ).fetchall()
                    if run["reply_to"] is not None:
                        ref = await (
                            await conn.execute(
                                (
                                    "SELECT COALESCE(m.task_id,r.task_id) AS task_id FROM "
                                    "kestri.messages m LEFT JOIN kestri.runs r ON r.id=m.run_id "
                                    "WHERE m.chat_id=%s AND m.telegram_id=%s ORDER BY m.id DESC "
                                    "LIMIT 1"
                                ),
                                (run["chat_id"], run["reply_to"]),
                            )
                        ).fetchone()
                        candidates = [t for t in candidates if ref and t["id"] == ref["task_id"]]
                    elif plan.target:
                        if plan.target not in text:
                            raise PolicyDenied("TargetMustComeFromOwner")
                        candidates = [
                            t
                            for t in candidates
                            if str(t["id"]).startswith(plan.target) or t["title"] == plan.target
                        ]
                    if len(candidates) != 1:
                        notice = (
                            "目标任务不明确，未作变更。请回复目标任务的约定/简报，"
                            "或指定 /tasks 中的任务 ID。"
                        )
                    else:
                        task = candidates[0]
                        if intent == "update":
                            if not any(
                                (
                                    plan.instructions,
                                    plan.local_time,
                                    plan.timezone,
                                    plan.weekdays,
                                    plan.title,
                                )
                            ):
                                raise PolicyDenied("MissingTaskChanges")
                            if plan.instructions:
                                if plan.instructions not in text:
                                    raise PolicyDenied("InstructionsMustComeFromOwner")
                                task["instructions"] += "\n用户修订：" + plan.instructions
                            if plan.timezone and plan.timezone not in text:
                                raise PolicyDenied("TimezoneMustComeFromOwner")
                            if plan.local_time and plan.local_time != requested_time(text):
                                raise PolicyDenied("TimeMustComeFromOwner")
                            if plan.weekdays and plan.weekdays != requested_weekdays(text):
                                raise PolicyDenied("WeekdaysMustComeFromOwner")
                            task["local_time"] = plan.local_time or task["local_time"]
                            task["timezone"] = plan.timezone or task["timezone"]
                            task["weekdays"] = plan.weekdays or task["weekdays"]
                            task["title"] = plan.title or task["title"]
                        else:
                            task["status"] = {
                                "pause": "paused",
                                "resume": "active",
                                "delete": "deleted",
                            }[intent]
                        task["next_due"] = next_occurrence(
                            now, task["local_time"], task["timezone"], task["weekdays"]
                        )
                        task["revision"] += 1
                        task = await (
                            await conn.execute(
                                (
                                    "UPDATE kestri.tasks SET "
                                    "title=%s,instructions=%s,timezone=%s,local_time=%s,weekdays=%s,catch_up_seconds=%s,status=%s,next_due=%s,revision=%s,updated_at=%s"
                                    ",restored=CASE WHEN %s THEN false ELSE restored END"
                                    " WHERE id=%s RETURNING *"
                                ),
                                (
                                    task["title"],
                                    task["instructions"],
                                    task["timezone"],
                                    task["local_time"],
                                    task["weekdays"],
                                    task["catch_up_seconds"],
                                    task["status"],
                                    task["next_due"],
                                    task["revision"],
                                    now,
                                    intent == "resume",
                                    task["id"],
                                ),
                            )
                        ).fetchone()
                        await conn.execute(
                            (
                                "UPDATE kestri.runs SET "
                                "status='cancelled',cancel_requested=true,finished_at=%s,error_type='AgreementChanged'"
                                " WHERE task_id=%s AND status='queued'"
                            ),
                            (now, task["id"] if task else None),
                        )
                if task:
                    notice = agreement(task)
                    await conn.execute(
                        "UPDATE kestri.runs SET task_id=%s WHERE id=%s", (task["id"], run["id"])
                    )
                notice = self.store.redactor.text(notice)
                await conn.execute(
                    (
                        "INSERT INTO kestri.task_changes(run_id,task_id,action,result) VALUES "
                        "(%s,%s,%s,%s)"
                    ),
                    (run["id"], task["id"] if task else None, plan.action, notice),
                )
                return notice

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
                    "UPDATE kestri.runs r SET "
                    "status='cancelled',cancel_requested=true,finished_at=%s,error_type='CatchUpExpired'"
                    " FROM kestri.tasks t WHERE r.task_id=t.id AND r.status='queued' AND "
                    "r.kind='background' AND "
                    "r.scheduled_for+make_interval(secs=>t.catch_up_seconds)<%s",
                    (now, now),
                )
                tasks = await (
                    await conn.execute(
                        (
                            "SELECT * FROM kestri.tasks WHERE chat_id=%s AND status='active' AND "
                            "next_due<=%s ORDER BY next_due FOR UPDATE"
                        ),
                        (self.settings.telegram_owner_id, now),
                    )
                ).fetchall()
                count = await (
                    await conn.execute(
                        "SELECT count(*) AS n FROM kestri.runs WHERE kind='background' AND status"
                        " IN ('queued','running')"
                    )
                ).fetchone()
                remaining = self.settings.background_queue_limit - (count["n"] if count else 0)
                for task in tasks:
                    latest = latest_occurrence(
                        now, task["local_time"], task["timezone"], task["weekdays"]
                    )
                    if latest < task["next_due"]:
                        continue
                    age = (now - latest).total_seconds()
                    active = await (
                        await conn.execute(
                            (
                                "SELECT id FROM kestri.runs WHERE task_id=%s AND "
                                "kind='background' AND status IN ('queued','running')"
                            ),
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
                            (
                                "INSERT INTO "
                                "kestri.runs(id,chat_id,message_id,request,status,kind,task_id,task_revision,scheduled_for)"
                                " VALUES (%s,%s,0,%s,'queued','background',%s,%s,%s) ON "
                                "CONFLICT(task_id,scheduled_for) DO NOTHING"
                            ),
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
                                now, task["local_time"], task["timezone"], task["weekdays"]
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
