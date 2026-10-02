"""Daily/weekly wall-clock schedules with explicit IANA zones and UTC identities."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


def occurrence(day: date, local_time: str, timezone: str) -> datetime | None:
    hour, minute = map(int, local_time.split(":"))
    local = datetime(
        day.year,
        day.month,
        day.day,
        hour,
        minute,
    )
    zone = ZoneInfo(timezone)
    # Earlier fold once; a nonexistent wall time is skipped rather than shifted silently.
    instant = local.replace(tzinfo=zone, fold=0).astimezone(UTC)
    return instant if instant.astimezone(zone).replace(tzinfo=None) == local else None


def next_occurrence(
    after: datetime, local_time: str, timezone: str, weekdays: list[int]
) -> datetime:
    day = after.astimezone(ZoneInfo(timezone)).date()
    for offset in range(15):
        candidate_day = day + timedelta(days=offset)
        if candidate_day.weekday() in weekdays:
            candidate = occurrence(candidate_day, local_time, timezone)
            if candidate is not None and candidate > after:
                return candidate
    raise ValueError("NoNextOccurrence")


def latest_occurrence(
    now: datetime, local_time: str, timezone: str, weekdays: list[int]
) -> datetime:
    day = now.astimezone(ZoneInfo(timezone)).date()
    for offset in range(15):
        candidate_day = day - timedelta(days=offset)
        if candidate_day.weekday() in weekdays:
            candidate = occurrence(candidate_day, local_time, timezone)
            if candidate is not None and candidate <= now:
                return candidate
    raise ValueError("NoPreviousOccurrence")


def requested_time(text: str) -> str | None:
    """Recognize explicit numeric/Chinese clock times without model invention."""
    import re

    clock = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", text)
    if clock:
        return f"{int(clock[1]):02}:{clock[2]}"
    chinese = re.search(
        r"([零一二三四五六七八九十两\d]+)点(?:(半)|([零一二三四五六七八九十两\d]+)分)?",
        text,
    )
    if chinese is None:
        return None

    def number(value: str) -> int:
        if value.isdigit():
            return int(value)
        digits = {
            "零": 0,
            "一": 1,
            "二": 2,
            "两": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
        }
        if "十" in value:
            left, right = value.split("十", 1)
            return (digits[left] if left else 1) * 10 + (digits[right] if right else 0)
        return digits[value]

    try:
        hour = number(chinese[1])
        if chinese[2]:
            minute = 30
        elif chinese[3]:
            minute = number(chinese[3])
        else:
            minute = 0
    except KeyError, ValueError:
        return None
    if re.search(r"下午|晚上|傍晚", text) and hour < 12:
        hour += 12
    return f"{hour:02}:{minute:02}" if 0 <= hour <= 23 and 0 <= minute <= 59 else None


def requested_weekdays(text: str) -> list[int] | None:
    import re

    if re.search(r"工作日|every weekday|weekdays", text, re.I):
        return list(range(5))
    if re.search(r"每天|每日|daily|every day", text, re.I):
        return list(range(7))
    mapping = {
        "一": 0,
        "二": 1,
        "三": 2,
        "四": 3,
        "五": 4,
        "六": 5,
        "日": 6,
        "天": 6,
    }
    days = {mapping[match] for match in re.findall(r"(?:每周|周|星期)([一二三四五六日天])", text)}
    for index, name in enumerate(
        ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    ):
        if re.search(r"\b" + name + r"\b", text, re.I):
            days.add(index)
    return sorted(days) if days else None
