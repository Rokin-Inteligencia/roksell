from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_STORE_TIMEZONE = "America/Sao_Paulo"


def normalize_store_timezone(value: str | None) -> str:
    candidate = (value or "").strip() or DEFAULT_STORE_TIMEZONE
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Invalid store timezone") from exc
    return candidate


def tzinfo_for_store(store) -> ZoneInfo:
    return ZoneInfo(normalize_store_timezone(getattr(store, "timezone", None)))

