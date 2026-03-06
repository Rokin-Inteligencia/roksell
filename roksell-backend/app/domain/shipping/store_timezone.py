from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_STORE_TIMEZONE = "America/Sao_Paulo"

# Mapeamento de nomes comuns/incorretos para IANA válido
TIMEZONE_ALIASES: dict[str, str] = {
    "America/Brasilia": "America/Sao_Paulo",
    "America/Brazil": "America/Sao_Paulo",
    "Brazil/East": "America/Sao_Paulo",
    "Brasilia": "America/Sao_Paulo",
    "São Paulo": "America/Sao_Paulo",
    "Sao Paulo": "America/Sao_Paulo",
}


def normalize_store_timezone(value: str | None) -> str:
    raw = (value or "").strip() or DEFAULT_STORE_TIMEZONE
    candidate = TIMEZONE_ALIASES.get(raw, raw)
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Invalid store timezone") from exc
    return candidate


def normalize_store_timezone_or_default(value: str | None) -> str:
    """Normaliza timezone; se inválido, retorna o default em vez de levantar exceção."""
    raw = (value or "").strip() or None
    if not raw:
        return DEFAULT_STORE_TIMEZONE
    candidate = TIMEZONE_ALIASES.get(raw, raw)
    try:
        ZoneInfo(candidate)
        return candidate
    except ZoneInfoNotFoundError:
        return DEFAULT_STORE_TIMEZONE


def tzinfo_for_store(store) -> ZoneInfo:
    return ZoneInfo(normalize_store_timezone_or_default(getattr(store, "timezone", None)))

