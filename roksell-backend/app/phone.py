from __future__ import annotations

import os

DEFAULT_COUNTRY_CODE = os.getenv("DEFAULT_PHONE_COUNTRY", "55").strip()


def _digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def normalize_phone(value: str | None) -> str:
    digits = _digits(value)
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) in (11, 12):
        digits = digits[1:]
    if DEFAULT_COUNTRY_CODE and not digits.startswith(DEFAULT_COUNTRY_CODE):
        if len(digits) in (10, 11):
            digits = f"{DEFAULT_COUNTRY_CODE}{digits}"
    return digits


def phone_candidates(value: str | None) -> list[str]:
    digits_raw = _digits(value)
    normalized = normalize_phone(value)
    candidates: set[str] = set()
    if digits_raw:
        candidates.add(digits_raw)
    if normalized:
        candidates.add(normalized)

    country = DEFAULT_COUNTRY_CODE
    if digits_raw and country and len(digits_raw) in (10, 11):
        candidates.add(f"{country}{digits_raw}")

    if normalized and country == "55" and normalized.startswith("55"):
        if len(normalized) == 12:
            candidates.add(normalized[:4] + "9" + normalized[4:])
        elif len(normalized) == 13 and normalized[4] == "9":
            candidates.add(normalized[:4] + normalized[5:])
    return list(candidates)
