from __future__ import annotations

import json
from typing import Iterable

ALLOWED_PAYMENT_METHODS = ("pix", "cash")


def normalize_payment_methods(methods: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in methods:
        method = str(item).strip().lower()
        if not method:
            continue
        if method not in ALLOWED_PAYMENT_METHODS:
            raise ValueError("Invalid payment method")
        if method not in result:
            result.append(method)
    if not result:
        raise ValueError("At least one payment method is required")
    return result


def load_payment_methods(raw: str | None) -> list[str]:
    if not raw:
        return list(ALLOWED_PAYMENT_METHODS)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return list(ALLOWED_PAYMENT_METHODS)
    if not isinstance(data, list):
        return list(ALLOWED_PAYMENT_METHODS)
    try:
        return normalize_payment_methods([str(item) for item in data])
    except ValueError:
        return list(ALLOWED_PAYMENT_METHODS)
