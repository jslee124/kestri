"""Anchored owner controls with literal targets; retrieval scores never authorize writes."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class NaturalMemoryControl:
    action: Literal["correct", "forget"]
    target: str
    content: str | None = None
    id_target: bool = False


def normalize_target(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split()).strip(
        " \"'“”‘’「」『』：:"
    )


def natural_control(text: str) -> NaturalMemoryControl | None:
    """Accept a complete direct command, not quoted, hypothetical, or embedded instructions."""
    text = text.strip()
    correction = re.fullmatch(
        r"(?:请)?(?:把|将)(?:关于)?(.+?)(?:这条|的)?记忆"
        r"(?:更正为|改成|改为|更新为|修改为)(.+?)[。！!]?",
        text,
        re.S,
    ) or re.fullmatch(
        r"(?:请)?更正记忆[ ：:]+(.+?)[ ]*(?:改成|改为|=>|→)[ ]*(.+?)[。！!]?",
        text,
        re.S,
    )
    if correction:
        target, content = correction.groups()
        return NaturalMemoryControl(
            "correct",
            target.strip(),
            content.strip(),
            id_target=text.startswith(("更正记忆", "请更正记忆")),
        )
    forgetting = re.fullmatch(
        r"(?:请)?(?:忘记|删除|移除)(?:关于)?(.+?)(?:这条|的)?记忆[。！!]?",
        text,
        re.S,
    ) or re.fullmatch(r"(?:请)?忘记记忆[ ：:]+(.+?)[。！!]?", text, re.S)
    if forgetting:
        return NaturalMemoryControl(
            "forget",
            forgetting[1].strip(),
            id_target=text.startswith(("忘记记忆", "请忘记记忆")),
        )
    return None
