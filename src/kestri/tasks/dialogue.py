"""Revalidate bounded task continuations from archived direct-owner control messages."""

import re
from dataclasses import dataclass
from typing import Any

from kestri.assistant.choices import current, issue, selection
from kestri.assistant.routing import supplement
from kestri.errors import PolicyDenied
from kestri.storage.store import Row
from kestri.tasks.intent import TaskAction


@dataclass(frozen=True)
class Continuation:
    token: str
    action: TaskAction
    text: str
    sources: tuple[str, ...]
    target: str | None
    revision: int | None
    plan: dict[str, Any] | None


async def prepare(conn: Any, run: Row) -> Continuation | None:
    state = await (
        await conn.execute(
            "SELECT memory_choice, memory_epoch FROM kestri.conversations WHERE chat_id = %s",
            (run["chat_id"],),
        )
    ).fetchone()
    if not state or not current(state["memory_choice"], state["memory_epoch"], "task"):
        return None
    choice = state["memory_choice"]
    selected = selection(run["request"])
    if selected:
        if choice["mode"] == "reference":
            return None
        token, index = selected
        if token and token != choice["token"]:
            raise PolicyDenied("TaskChoiceExpired")
        if index >= len(choice["targets"]):
            raise PolicyDenied("TaskChoiceUnavailable")
        target = choice["targets"][index]
        plan = choice["plan"]
        if plan and plan["action"] == "clarify":
            plan = None
    elif choice["mode"] in {"supplement", "reference"} and supplement(run["request"]):
        if choice["mode"] == "reference" and not re.match(
            r"(?:请)?(?:改到|改成|改为|时间改到)", run["request"]
        ):
            return None
        if len(choice["targets"]) > 1:
            raise PolicyDenied("TaskTargetStillAmbiguous")
        target = choice["targets"][0] if choice["targets"] else None
        plan = None
    else:
        return None
    sources = tuple(choice["sources"])
    if not 1 <= len(sources) <= 3:
        raise PolicyDenied("TaskContinuationTooLong")
    rows = await (
        await conn.execute(
            """
            SELECT r.id, r.request
            FROM kestri.runs AS r
            WHERE r.chat_id = %s AND r.id = ANY(%s::uuid[])
              AND r.kind = 'task_control' AND NOT r.history_expired
              AND EXISTS (
                  SELECT 1 FROM kestri.messages AS m
                  WHERE m.run_id = r.id AND m.direction = 'in' AND m.provenance = 'direct'
              )
            """,
            (run["chat_id"], list(sources)),
        )
    ).fetchall()
    requests = {str(row["id"]): row["request"] for row in rows}
    if len(requests) != len(sources):
        raise PolicyDenied("TaskContinuationSourceUnavailable")
    text = "\n".join(requests[source] for source in sources)
    if choice["mode"] == "reference":
        text = run["request"]
    elif not selected:
        text += "\n" + run["request"]
    if len(text) > 4000:
        raise PolicyDenied("TaskContinuationTooLong")
    return Continuation(
        token=choice["token"],
        action=choice["action"],
        text=text,
        sources=sources,
        target=target["id"] if target else None,
        revision=target["revision"] if target else None,
        plan=plan,
    )


async def stage(
    conn: Any,
    run: Row,
    action: TaskAction,
    plan: dict[str, Any],
    targets: list[Row],
    *,
    mode: str,
    continuation: Continuation | None = None,
) -> str:
    sources = list(continuation.sources) if continuation else []
    sources.append(str(run["id"]))
    if len(sources) > 3:
        return "补充次数已达上限，未作变更。请重新发送完整任务请求。"
    await issue(
        conn,
        run["chat_id"],
        {
            "domain": "task",
            "mode": mode,
            "action": action,
            "plan": plan,
            "run_id": str(run["id"]),
            "sources": sources,
            "targets": [
                {"id": str(task["id"]), "revision": task["revision"]} for task in targets[:5]
            ],
        },
    )
    if mode == "supplement":
        heading = "尚未创建任务。" if action == "create" else "尚未修改任务。"
        question = plan.get("clarification") or (
            "请补充明确的时间或 IANA 时区，例如“晚上八点”或“Asia/Shanghai”。"
        )
        return heading + question + "\n十分钟内有效，也可以重新发送完整指令。"
    lines = [
        "目标任务不明确，未作变更。",
        "请选择对应任务，回复“第二个”或点击按钮；十分钟内有效。",
        "",
    ]
    lines.extend(
        f"{index + 1}. {task['title']} · 编号：{str(task['id'])[:8]}"
        for index, task in enumerate(targets[:5])
    )
    if len(targets) > 5:
        lines.append("这里只显示前五项；其他任务请明确提供编号。")
    return "\n".join(lines)
