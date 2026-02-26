import json
from datetime import date


def load_store_closed_dates(raw: str | None) -> list[date]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    parsed: list[date] = []
    for item in data:
        try:
            parsed.append(date.fromisoformat(str(item)))
        except ValueError:
            continue
    unique_sorted = sorted({d.isoformat() for d in parsed})
    return [date.fromisoformat(value) for value in unique_sorted]


def dump_store_closed_dates(values: list[date] | None) -> str | None:
    if values is None:
        return None
    unique_sorted = sorted({d.isoformat() for d in values})
    return json.dumps(unique_sorted, ensure_ascii=False)
