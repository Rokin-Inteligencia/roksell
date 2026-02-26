from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Iterable


def normalize_operating_hours(items: Iterable[dict]) -> list[dict]:
    normalized: dict[int, dict] = {}
    for item in items:
        day_raw = item.get("day")
        if day_raw is None:
            raise ValueError("Missing day")
        day = int(day_raw)
        if day < 0 or day > 6:
            raise ValueError("Invalid day")

        enabled = bool(item.get("enabled", False))
        open_time = _normalize_time(item.get("open"))
        close_time = _normalize_time(item.get("close"))

        if enabled and (open_time is None or close_time is None):
            raise ValueError("Missing open/close time")
        if enabled and _time_to_minutes(close_time) <= _time_to_minutes(open_time):
            raise ValueError("Invalid time range")

        normalized[day] = {
            "day": day,
            "enabled": enabled,
            "open": open_time,
            "close": close_time,
        }

    return [normalized[key] for key in sorted(normalized.keys())]


def load_operating_hours(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    try:
        return normalize_operating_hours(data)
    except ValueError:
        return []


def is_open_now(operating_hours: list[dict] | None, tz_offset_hours: int = -3) -> bool:
    if not operating_hours:
        return True
    now = datetime.now(timezone(timedelta(hours=tz_offset_hours)))
    weekday = now.weekday()
    today = next((item for item in operating_hours if item.get("day") == weekday), None)
    if not today or not today.get("enabled"):
        return False
    open_time = today.get("open")
    close_time = today.get("close")
    if not open_time or not close_time:
        return False
    open_minutes = _time_to_minutes(open_time)
    close_minutes = _time_to_minutes(close_time)
    now_minutes = now.hour * 60 + now.minute
    return open_minutes <= now_minutes < close_minutes


def _normalize_time(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    parts = cleaned.split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _time_to_minutes(value: str | None) -> int:
    if not value:
        return 0
    parts = value.split(":")
    if len(parts) != 2:
        return 0
    return int(parts[0]) * 60 + int(parts[1])
