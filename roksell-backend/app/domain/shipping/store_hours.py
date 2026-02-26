import json
from typing import Iterable

from app.domain.config.operating_hours import normalize_operating_hours


def load_store_operating_hours(raw: str | None) -> list[dict]:
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


def dump_store_operating_hours(values: Iterable[dict] | None) -> str | None:
    if values is None:
        return None
    normalized = normalize_operating_hours(values)
    return json.dumps(normalized, ensure_ascii=False)
