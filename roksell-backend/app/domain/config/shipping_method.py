from __future__ import annotations

ALLOWED_SHIPPING_METHODS = ("distance", "district")


def normalize_shipping_method(value: str | None) -> str:
    if not value:
        return "distance"
    method = value.strip().lower()
    if method not in ALLOWED_SHIPPING_METHODS:
        raise ValueError("Invalid shipping method")
    return method


def load_shipping_method(raw: str | None) -> str:
    if not raw:
        return "distance"
    try:
        return normalize_shipping_method(raw)
    except ValueError:
        return "distance"
