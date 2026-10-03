"""Owner task mutations, split into authority, target resolution and commit helpers."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from kestri.assistant.choices import issue
from kestri.errors import PolicyDenied
from kestri.settings import ResearchSettings
from kestri.storage.store import Row, Store
from kestri.tasks.dialogue import Continuation, prepare, stage
from kestri.tasks.intent import TaskAction, task_intent
from kestri.tasks.presentation import agreement
from kestri.tasks.schedule import next_occurrence, requested_time, requested_weekdays
from kestri.tasks.service import TaskPlan, list_tasks


async def targets(
    conn: Any, run: Row, plan: TaskPlan, text: str, continuation: Continuation | None
) -> list[Row]:
    rows: list[Row] = await (
        await conn.execute(
            """
            SELECT * FROM kestri.tasks
            WHERE chat_id = %s AND status != 'deleted'
            ORDER BY created_at, id
            FOR UPDATE
            """,
            (run["chat_id"],),
        )
    ).fetchall()
    if continuation and continuation.target:
        rows = [task for task in rows if str(task["id"]) == continuation.target]
        if len(rows) != 1 or rows[0]["revision"] != continuation.revision:
            raise PolicyDenied("TaskChoiceTargetChanged")
        return rows
    if run["reply_to"] is not None:
        reference = await (
            await conn.execute(
                """
                SELECT COALESCE(m.task_id, r.task_id) AS task_id
                FROM kestri.messages AS m
                LEFT JOIN kestri.runs AS r ON r.id = m.run_id
                WHERE m.chat_id = %s AND m.telegram_id = %s
                ORDER BY m.id DESC
                LIMIT 1
                """,
                (run["chat_id"], run["reply_to"]),
            )
        ).fetchone()
        return [task for task in rows if reference and task["id"] == reference["task_id"]]
    if not plan.target:
        return rows
    if plan.target not in text:
        raise PolicyDenied("TargetMustComeFromOwner")
    return [
        task
        for task in rows
        if str(task["id"]).startswith(plan.target)
        or (len(plan.target) >= 2 and plan.target.casefold() in task["title"].casefold())
    ]


def validate_update(plan: TaskPlan, text: str) -> None:
    fields = (plan.instructions, plan.local_time, plan.timezone, plan.weekdays, plan.title)
    if not any(fields):
        raise PolicyDenied("MissingTaskChanges")
    literal_fields = (
        (plan.instructions, "InstructionsMustComeFromOwner"),
        (plan.timezone, "TimezoneMustComeFromOwner"),
        (plan.title, "TitleMustComeFromOwner"),
    )
    for value, error in literal_fields:
        if value and value not in text:
            raise PolicyDenied(error)
    if plan.local_time and plan.local_time != requested_time(text):
        raise PolicyDenied("TimeMustComeFromOwner")
    if plan.weekdays and plan.weekdays != requested_weekdays(text):
        raise PolicyDenied("WeekdaysMustComeFromOwner")


async def create(
    conn: Any, run: Row, plan: TaskPlan, settings: ResearchSettings, text: str, now: datetime
) -> tuple[Row | None, str]:
    zone = plan.timezone or settings.owner_timezone
    complete = zone and plan.local_time and plan.weekdays and plan.instructions
    owner_schedule = plan.local_time == requested_time(
        text
    ) and plan.weekdays == requested_weekdays(text)
    if not complete or not owner_schedule:
        return None, "尚未创建任务。请补充每日/每周时间、时区和内容。"
    assert zone and plan.local_time and plan.weekdays and plan.instructions
    if plan.timezone and plan.timezone not in text and plan.timezone != settings.owner_timezone:
        return None, "尚未创建任务。请明确 IANA 时区，或配置主人时区。"
    if plan.instructions not in text:
        raise PolicyDenied("InstructionsMustComeFromOwner")
    count = await (
        await conn.execute(
            "SELECT count(*) AS n FROM kestri.tasks WHERE chat_id = %s AND status != 'deleted'",
            (run["chat_id"],),
        )
    ).fetchone()
    if count["n"] >= settings.task_limit:
        return None, "持续任务数量已达上限；未创建任务。"
    task = await (
        await conn.execute(
            """
            INSERT INTO kestri.tasks (
                id, chat_id, title, instructions, timezone, local_time, weekdays,
                catch_up_seconds, status, next_due, authorized_run_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 21600, 'active', %s, %s)
            RETURNING *
            """,
            (
                uuid4(),
                run["chat_id"],
                plan.title or "个人简报",
                plan.instructions,
                zone,
                plan.local_time,
                plan.weekdays,
                next_occurrence(now, plan.local_time, zone, plan.weekdays),
                run["id"],
            ),
        )
    ).fetchone()
    return task, ""


async def change(
    conn: Any, task: Row, plan: TaskPlan, intent: TaskAction, text: str, now: datetime
) -> Row:
    if intent == "update":
        validate_update(plan, text)
        if plan.instructions:
            task["instructions"] += "\n用户修订：" + plan.instructions
        task["local_time"] = plan.local_time or task["local_time"]
        task["timezone"] = plan.timezone or task["timezone"]
        task["weekdays"] = plan.weekdays or task["weekdays"]
        task["title"] = plan.title or task["title"]
    else:
        task["status"] = {"pause": "paused", "resume": "active", "delete": "deleted"}[intent]
    due = next_occurrence(now, task["local_time"], task["timezone"], task["weekdays"])
    updated: Row | None = await (
        await conn.execute(
            """
            UPDATE kestri.tasks
            SET title = %s, instructions = %s, timezone = %s, local_time = %s,
                weekdays = %s, status = %s, next_due = %s,
                revision = revision + 1, updated_at = %s,
                restored = CASE WHEN %s THEN false ELSE restored END
            WHERE id = %s
            RETURNING *
            """,
            (
                task["title"],
                task["instructions"],
                task["timezone"],
                task["local_time"],
                task["weekdays"],
                task["status"],
                due,
                now,
                intent == "resume",
                task["id"],
            ),
        )
    ).fetchone()
    assert updated is not None
    await conn.execute(
        """
        UPDATE kestri.runs
        SET status = 'cancelled', cancel_requested = true,
            finished_at = %s, error_type = 'AgreementChanged'
        WHERE task_id = %s AND status = 'queued'
        """,
        (now, task["id"]),
    )
    return updated


async def apply_control(
    store: Store,
    settings: ResearchSettings,
    run: Row,
    plan: TaskPlan,
    intent: TaskAction,
    now: datetime,
    continuation: Continuation | None = None,
) -> str:
    async with store.pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT chat_id FROM kestri.conversations WHERE chat_id = %s FOR UPDATE",
                (run["chat_id"],),
            )
            current = await (
                await conn.execute(
                    "SELECT * FROM kestri.runs WHERE id = %s FOR UPDATE", (run["id"],)
                )
            ).fetchone()
            if not current or current["status"] != "running" or current["cancel_requested"]:
                raise PolicyDenied("RunInactive")
            prior = await (
                await conn.execute(
                    "SELECT result FROM kestri.task_changes WHERE run_id = %s", (run["id"],)
                )
            ).fetchone()
            if prior:
                return str(prior["result"])
            source = await (
                await conn.execute(
                    "SELECT provenance FROM kestri.messages WHERE run_id = %s AND direction = 'in'",
                    (run["id"],),
                )
            ).fetchone()
            if (
                current["kind"] != "task_control"
                or current["request"] != run["request"]
                or not source
                or source["provenance"] != "direct"
            ):
                raise PolicyDenied("TaskAuthorizationUnavailable")
            if continuation and await prepare(conn, run) != continuation:
                raise PolicyDenied("TaskChoiceChanged")
            text = continuation.text if continuation else run["request"]
            authority = (
                continuation.action
                if continuation
                else task_intent(text, task_reference=run["reply_to"] is not None)
            )
            if authority != intent or plan.action not in {intent, "clarify"}:
                raise PolicyDenied("TaskActionMismatch")
            if intent in {"pause", "resume", "delete", "list"} and any(
                (plan.title, plan.instructions, plan.local_time, plan.timezone, plan.weekdays)
            ):
                raise PolicyDenied("UnexpectedTaskFields")
            task = None
            notice = ""
            if intent == "list":
                notice = await list_tasks(conn, run["chat_id"])
            else:
                candidates = (
                    [] if intent == "create" else await targets(conn, run, plan, text, continuation)
                )
                if plan.action == "clarify":
                    mode = "select" if len(candidates) > 1 else "supplement"
                    notice = await stage(
                        conn,
                        run,
                        intent,
                        plan.model_dump(),
                        candidates,
                        mode=mode,
                        continuation=continuation,
                    )
                elif intent == "create":
                    task, notice = await create(conn, run, plan, settings, text, now)
                    if task is None and "上限" not in notice:
                        pending_plan = plan.model_dump()
                        pending_plan["clarification"] = notice.removeprefix("尚未创建任务。")
                        notice = await stage(
                            conn,
                            run,
                            intent,
                            pending_plan,
                            [],
                            mode="supplement",
                            continuation=continuation,
                        )
                elif len(candidates) != 1:
                    notice = (
                        await stage(
                            conn,
                            run,
                            intent,
                            plan.model_dump(),
                            candidates,
                            mode="select",
                            continuation=continuation,
                        )
                        if candidates
                        else "没有找到对应任务，未作变更。请查看任务列表后明确编号。"
                    )
                else:
                    task = await change(conn, candidates[0], plan, intent, text, now)
            if task:
                notice = agreement(task)
                await conn.execute(
                    "UPDATE kestri.runs SET task_id = %s WHERE id = %s", (task["id"], run["id"])
                )
                await conn.execute(
                    "UPDATE kestri.conversations SET memory_choice = NULL WHERE chat_id = %s",
                    (run["chat_id"],),
                )
                if task["status"] != "deleted":
                    await issue(
                        conn,
                        run["chat_id"],
                        {
                            "domain": "task",
                            "mode": "reference",
                            "action": "update",
                            "plan": None,
                            "run_id": str(run["id"]),
                            "sources": [str(run["id"])],
                            "targets": [{"id": str(task["id"]), "revision": task["revision"]}],
                        },
                    )
            notice = store.redactor.text(notice)
            await conn.execute(
                """
                INSERT INTO kestri.task_changes (run_id, task_id, action, result)
                VALUES (%s, %s, %s, %s)
                """,
                (run["id"], task["id"] if task else None, plan.action, notice),
            )
            return notice
