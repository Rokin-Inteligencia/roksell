from __future__ import annotations

ALLOWED_AVAILABILITY_STATUSES = ("available", "order", "unavailable")


def normalize_availability_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized not in ALLOWED_AVAILABILITY_STATUSES:
        raise ValueError(f"Invalid availability_status: {value}")
    return normalized


def resolve_availability_status(value: str | None, block_sale: bool | None = None) -> str:
    if value is not None:
        normalized = normalize_availability_status(value)
        if normalized is None:
            return "available"
        return normalized
    if block_sale:
        return "order"
    return "available"


def is_available_for_sale(value: str | None, block_sale: bool | None = None) -> bool:
    return resolve_availability_status(value, block_sale) == "available"


def block_sale_from_status(value: str | None) -> bool:
    normalized = normalize_availability_status(value)
    if normalized is None:
        return False
    return normalized != "available"
