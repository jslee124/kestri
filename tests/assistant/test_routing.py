"""Labeled colloquial requests and counterexamples with explicit operation expectations."""

from datetime import UTC, datetime, timedelta

import pytest

from kestri.assistant.routing import route

CASES = [
    ("我有哪些任务？", "tasks", "foreground"),
    ("我现在有什么任务", "tasks", "foreground"),
    ("查看我的任务", "tasks", "foreground"),
    ("你现在在做什么？", "status", "foreground"),
    ("现在正在做什么", "status", "foreground"),
    ("开始新话题", "new", "foreground"),
    ("换个话题", "new", "foreground"),
    ("帮我停止当前执行", "stop", "foreground"),
    ("你能做什么", "help", "foreground"),
    ("本月花费", "usage", "foreground"),
    ("查看最近执行记录", "runs", "foreground"),
    ("暂停每天的新闻简报", None, "task_control"),
    ("修改新闻简报时间", None, "task_control"),
    ("每天晚上八点给我新闻简报", None, "task_control"),
    ("开启自动记忆", None, "memory_control"),
    ("你现在记住了我哪些事情", None, "memory_control"),
    ("只依据有效记忆回答饮食偏好", None, "foreground"),
    ("不要暂停新闻简报", None, "foreground"),
    ("我不想删除任务", None, "foreground"),
    ("如果我暂停新闻简报会怎样", None, "foreground"),
    ("解释如何停止当前执行", None, "foreground"),
    ("他说“开始新话题”", None, "foreground"),
    ("暂停简报并删除任务", "clarify", "foreground"),
    ("暂停新闻简报并开启自动记忆", "clarify", "foreground"),
    ("暂停简报，然后开始新话题", "clarify", "foreground"),
]


@pytest.mark.parametrize(("text", "command", "kind"), CASES)
def test_labeled_control_routes(text: str, command: str | None, kind: str) -> None:
    selected = route(text, direct=True, reply=False, state=None)
    assert (selected.command, selected.kind) == (command, kind)


def test_choice_domain_and_explicit_reference_changes() -> None:
    choice = {
        "domain": "task",
        "mode": "reference",
        "epoch": 2,
        "expires": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
    }
    state = {"memory_epoch": 2, "memory_choice": choice}
    assert route("改到晚上八点", direct=True, reply=False, state=state).kind == "task_control"
    assert route("晚上八点", direct=True, reply=False, state=state).kind == "foreground"
    choice["mode"] = "select"
    assert route("第二个", direct=True, reply=False, state=state).kind == "task_control"
    assert route("第二个新闻不错", direct=True, reply=False, state=state).kind == "foreground"
    assert route("第二个", direct=False, reply=False, state=state).kind == "foreground"
