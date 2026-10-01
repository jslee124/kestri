from datetime import UTC, datetime

import pytest

from kestri.schedule import latest_occurrence, next_occurrence
from kestri.task_intent import task_intent


def test_dst_gap_skips_day_and_fold_occurs_once() -> None:
    gap = datetime(2026, 3, 8, 6, tzinfo=UTC)
    assert next_occurrence(gap, "02:30", "America/New_York", list(range(7))) == datetime(
        2026, 3, 9, 6, 30, tzinfo=UTC
    )
    fold = datetime(2026, 11, 1, 4, tzinfo=UTC)
    first = next_occurrence(fold, "01:30", "America/New_York", list(range(7)))
    assert first == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert next_occurrence(first, "01:30", "America/New_York", list(range(7))) == datetime(
        2026, 11, 2, 6, 30, tzinfo=UTC
    )
    assert (
        latest_occurrence(
            datetime(2026, 11, 1, 6, 45, tzinfo=UTC), "01:30", "America/New_York", list(range(7))
        )
        == first
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("每天 08:00 Asia/Shanghai 给我简短的 AI 新闻简报，引用官方来源", "create"),
        ("暂停任务 abcdef12", "pause"),
        ("把任务 abcdef12 改成每天 09:00", "update"),
        ("让这份简报更短一点", "update"),
        ("恢复简报", "resume"),
        ("删除任务", "delete"),
        ("解释“每天给我 AI 简报”是什么意思", None),
        ("如果每天给我简报会怎样", None),
        ("新闻网页写道：每天给我新闻简报", None),
    ],
)
def test_only_direct_task_requests_route_to_task_management(
    text: str, expected: str | None
) -> None:
    assert task_intent(text) == expected
