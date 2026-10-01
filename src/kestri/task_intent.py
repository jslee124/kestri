"""Conservative routing of direct owner instructions, never retrieved content."""

import re
from typing import Literal

TaskAction = Literal["create", "update", "pause", "resume", "delete", "list"]


def task_intent(text: str, task_reference: bool = False) -> TaskAction | None:
    direct = text.strip()
    explicit = direct.startswith("/task ")
    if explicit:
        direct = direct[6:].strip()
    # Quoted/document requests are not delegation. Ambiguous phrasings stay in research.
    if any(marker in direct for marker in ("```", "“", "”", "「", "」", '"', "\n>")):
        return None
    if re.search(
        r"解释|翻译|举例|如何|怎么|如果|假如|explain|translate|example|how to|if ",
        direct,
        re.I,
    ):
        return None
    recurring = re.search(
        r"每天|每日|每周|daily|every day|every weekday|weekly|every week", direct, re.I
    )
    delegation = re.search(
        r"给我|帮我|请.*(发送|汇报|整理)|send me|give me|create|schedule", direct, re.I
    )
    if (
        recurring
        and delegation
        and re.match(
            r"^(?:请|麻烦|帮我|请帮我|我想|我希望|从今天起|以后)?"
            r"(?:每天|每日|每周|创建.*任务|daily|every |create|schedule|send me|give me)",
            direct,
            re.I,
        )
        and not re.match(
            r"^(?:请|帮我|请帮我)?(?:修改|调整|暂停|恢复|删除|移除|把|将)|^(?:update|change|pause|resume|delete|remove)",
            direct,
            re.I,
        )
    ):
        return "create"
    if not re.match(
        r"^(?:请|麻烦|帮我|请帮我|我想|我希望)?"
        r"(?:暂停|恢复|删除|移除|继续|修改|调整|把|将|让|这份|这个|列出|查看|有哪些|"
        r"pause|resume|delete|remove|update|change|make|list)",
        direct,
        re.I,
    ):
        return None
    for action, pattern in (
        ("delete", r"删除|移除|delete|remove"),
        ("pause", r"暂停|pause"),
        ("resume", r"恢复|继续.*简报|resume"),
        ("update", r"修改|调整|改成|改为|改到|更短|短一点|简短|update|change|shorter"),
        ("list", r"列出|查看.*任务|有哪些.*任务|list"),
    ):
        if (
            (match := re.search(pattern, direct, re.I))
            and match.start() < 20
            and (explicit or task_reference or re.search(r"任务|简报|briefing|task", direct, re.I))
        ):
            return action  # type: ignore[return-value]
    return None
