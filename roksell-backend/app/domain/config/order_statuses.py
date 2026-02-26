from __future__ import annotations

import json
import re
import unicodedata
from typing import Iterable

DEFAULT_ORDER_STATUS = "received"
REQUIRED_ORDER_STATUS = "canceled"
DEFAULT_ORDER_STATUSES = [
    "received",
    "confirmed",
    "preparing",
    "ready",
    "on_route",
    "delivered",
    "completed",
    "canceled",
]
DEFAULT_ORDER_FINAL_STATUSES = ["completed", "canceled"]
COLOR_PATTERN = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
STATUS_ALIAS_MAP = {
    "recebido": "received",
    "confirmado": "confirmed",
    "preparando": "preparing",
    "pronto": "ready",
    "a_caminho": "on_route",
    "em_rota": "on_route",
    "entregue": "delivered",
    "concluido": "completed",
    "cancelado": "canceled",
}


def _normalize_label(value: str) -> str:
    normalized = value.strip().lower()
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    normalized = normalized.replace("-", " ").replace("_", " ")
    normalized = "".join(
        ch
        for ch in normalized
        if ch.isalnum() or ch.isspace()
    ).strip()
    normalized = normalized.replace(" ", "_")
    return normalized


def normalize_order_statuses(statuses: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in statuses:
        raw = str(item).strip()
        if not raw:
            continue
        key = _normalize_label(raw)
        value = STATUS_ALIAS_MAP.get(key, raw)
        if not value:
            continue
        if value not in result:
            result.append(value)
    if REQUIRED_ORDER_STATUS not in result:
        result.append(REQUIRED_ORDER_STATUS)
    if not result:
        raise ValueError("At least one order status is required")
    return result


def normalize_order_final_statuses(final_statuses: Iterable[str], statuses: Iterable[str] | None) -> list[str]:
    status_source = statuses or []
    status_set = {str(item).strip() for item in status_source if str(item).strip()}
    result: list[str] = []
    for item in final_statuses:
        value = str(item).strip()
        if not value or value not in status_set:
            continue
        if value not in result:
            result.append(value)
    if REQUIRED_ORDER_STATUS in status_set and REQUIRED_ORDER_STATUS not in result:
        result.append(REQUIRED_ORDER_STATUS)
    return result


def load_order_statuses(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_ORDER_STATUSES)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return list(DEFAULT_ORDER_STATUSES)
    if not isinstance(data, list):
        return list(DEFAULT_ORDER_STATUSES)
    try:
        return normalize_order_statuses([str(item) for item in data])
    except ValueError:
        return list(DEFAULT_ORDER_STATUSES)


def load_order_final_statuses(raw: str | None, statuses: Iterable[str]) -> list[str]:
    default = normalize_order_final_statuses(DEFAULT_ORDER_FINAL_STATUSES, statuses)
    if not raw:
        return default
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return default
    if not isinstance(data, list):
        return default
    result = normalize_order_final_statuses([str(item) for item in data], statuses)
    return result or default


def default_order_status(statuses: list[str]) -> str:
    if DEFAULT_ORDER_STATUS in statuses:
        return DEFAULT_ORDER_STATUS
    for item in statuses:
        if item != REQUIRED_ORDER_STATUS:
            return item
    return statuses[0] if statuses else DEFAULT_ORDER_STATUS


def normalize_order_status_colors(colors: dict[str, str], statuses: Iterable[str]) -> dict[str, str]:
    status_set = {str(item).strip() for item in statuses if str(item).strip()}
    result: dict[str, str] = {}
    for key, value in colors.items():
        status = str(key).strip()
        if not status or status not in status_set:
            continue
        color = str(value).strip()
        if not color:
            continue
        if not COLOR_PATTERN.match(color):
            raise ValueError(f"Invalid color for status {status}")
        if len(color) == 4:
            color = f"#{color[1]}{color[1]}{color[2]}{color[2]}{color[3]}{color[3]}"
        result[status] = color.lower()
    return result


def load_order_status_colors(raw: str | None, statuses: Iterable[str]) -> dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    try:
        return normalize_order_status_colors({str(k): str(v) for k, v in data.items()}, statuses)
    except ValueError:
        return {}
