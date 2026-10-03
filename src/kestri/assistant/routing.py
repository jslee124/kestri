"""One conservative entry for direct owner controls and issued continuations."""

import re
from dataclasses import dataclass
from typing import Any

from kestri.assistant.choices import current, selection
from kestri.integrations.telegram import command_for
from kestri.memory.management import direct_control, management_intent
from kestri.memory.service import memory_instruction
from kestri.tasks.intent import task_intent


@dataclass(frozen=True)
class Route:
    command: str | None = None
    kind: str = "foreground"


def runtime_command(text: str) -> str | None:
    text = text.strip().rstrip("。？！!?")
    aliases = {
        "tasks": (
            r"(?:我)?(?:现在)?(?:有|都有哪些|有哪些|有什么|查看|列出|看看)"
            r"(?:我)?(?:的)?(?:持续|定时)?任务"
        ),
        "status": (
            r"(?:你)?(?:现在|当前)(?:正在|在)?(?:做什么|干什么|忙什么)"
            r"|查看(?:当前|执行)?状态"
        ),
        "runs": r"(?:查看|列出|看看)(?:最近|之前)(?:的)?执行(?:记录)?",
        "usage": (
            r"(?:查看|看看)?(?:本月|这个月)(?:的)?(?:用量|花费|费用)"
            r"|(?:这个月|本月)花了多少钱"
        ),
        "new": r"(?:请|帮我)?(?:开始|开启|换|新建)(?:一个)?(?:新话题|新对话)|换个话题",
        "stop": r"(?:请|帮我)?(?:停止|停下|结束|取消)(?:一下)?(?:当前|这次|正在进行的)执行",
        "help": r"(?:你)?(?:能做什么|可以做什么|有什么功能)|(?:查看|显示)?(?:使用)?帮助",
    }
    return next(
        (command for command, pattern in aliases.items() if re.fullmatch(pattern, text)), None
    )


def supplement(text: str) -> bool:
    """Only explicit time/day/zone fragments are accepted as pending task supplements."""
    if re.fullmatch(r"UTC|[A-Za-z_]+/[A-Za-z_]+", text.strip()):
        return True
    return bool(
        re.fullmatch(
            r"(?:请)?(?:改到|改成|改为|时间改到|时间是|就)?"
            r"(?:每天|每日|每周[一二三四五六日天])?\s*"
            r"(?:(?:早上|上午|中午|下午|晚上|傍晚)?"
            r"(?:[零一二三四五六七八九十两\d]+点(?:半|[零一二三四五六七八九十两\d]+分)?|\d{1,2}:\d{2}))"
            r"(?:\s+(?:UTC|[A-Za-z_]+/[A-Za-z_]+))?[。！!]?",
            text.strip(),
        )
    )


def route(
    text: str,
    *,
    direct: bool,
    reply: bool,
    state: dict[str, Any] | None,
) -> Route:
    command = command_for(text)
    if not direct:
        if command in {"help", "start", "status", "runs", "tasks", "usage"}:
            return Route(command)
        return Route("denied" if command else None)
    if direct_control(text):
        command = command or runtime_command(text)
    if memory_instruction(text) and command in {"remember", "correct", "forget"}:
        return Route(kind="memory_control")
    if command and command != "task":
        return Route(command, "memory_control" if memory_instruction(text) else "foreground")
    choice = state.get("memory_choice") if state else None
    epoch = state["memory_epoch"] if state else 0
    task_choice = current(choice, epoch, "task")
    reference_change = bool(re.match(r"(?:请)?(?:改到|改成|改为|时间改到)", text))
    accepts_supplement = (
        task_choice and choice is not None and (choice["mode"] != "reference" or reference_change)
    )
    is_followup = selection(text) is not None or (accepts_supplement and supplement(text))
    if text.startswith("选择任务 ") or (task_choice and is_followup):
        return Route(kind="task_control")
    memory = memory_instruction(text)
    memory_management = management_intent(text)
    task = task_intent(text, task_reference=reply)
    if memory_management and task:
        return Route("clarify")
    if task and re.search(r"并|同时|然后|再", text):
        operations = re.findall(r"暂停|恢复|删除|移除|修改|调整|开始新话题|停止当前执行", text)
        if len(operations) > 1:
            return Route("clarify")
    if memory or memory_management:
        return Route(kind="memory_control")
    return Route(kind="task_control" if task else "foreground")
