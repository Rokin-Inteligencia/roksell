"""
Serviço de onboarding do admin: estado do onboarding, conclusão e modo teste.
O router admin apenas orquestra (HTTP, Depends) e chama este serviço.
"""
from __future__ import annotations

import json
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.domain.shipping.store_hours import dump_store_operating_hours, load_store_operating_hours
from app.domain.shipping.store_timezone import DEFAULT_STORE_TIMEZONE
from app.domain.tenancy.access import ensure_unique_store_slug, user_accessible_store_ids
from app.phone import normalize_phone
from app.services.shipping_distance import _geocode_with_nominatim

ONBOARDING_REQUIRED_ORIGINS = frozenset({"landing_page", "automatic_webhook"})
ONBOARDING_DEFAULT_LAT = -23.55052
ONBOARDING_DEFAULT_LON = -46.633308
ONBOARDING_FORCE_TEST_MODE = "force_first_access_test"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_postal_code(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if len(digits) != 8:
        raise HTTPException(status_code=400, detail="CEP invalido")
    return digits


def _normalize_state(value: str) -> str:
    cleaned = _normalize_optional_text(value)
    if not cleaned:
        raise HTTPException(status_code=400, detail="UF invalida")
    normalized = cleaned.upper()
    if len(normalized) != 2:
        raise HTTPException(status_code=400, detail="UF invalida")
    return normalized


def _normalize_person_type(value: str) -> models.CustomerPersonType:
    cleaned = (value or "").strip().lower()
    if cleaned in {"pf", "cpf", "individual", "pessoa_fisica", "pessoa-fisica", "fisica"}:
        return models.CustomerPersonType.individual
    if cleaned in {"pj", "cnpj", "company", "pessoa_juridica", "pessoa-juridica", "juridica", "empresa"}:
        return models.CustomerPersonType.company
    raise HTTPException(status_code=400, detail="Tipo de pessoa invalido")


def _normalize_document(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if not digits:
        raise HTTPException(status_code=400, detail="Documento obrigatorio")
    return digits


def _validate_document(person_type: models.CustomerPersonType, document: str) -> None:
    if person_type == models.CustomerPersonType.individual and len(document) != 11:
        raise HTTPException(status_code=400, detail="CPF deve ter 11 digitos")
    if person_type == models.CustomerPersonType.company and len(document) != 14:
        raise HTTPException(status_code=400, detail="CNPJ deve ter 14 digitos")


def _dump_operating_hours(values: list[schemas.OperatingHoursDay]) -> str:
    try:
        raw = dump_store_operating_hours(
            [item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in values]
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Horario de funcionamento invalido") from exc
    if not raw:
        raise HTTPException(status_code=400, detail="Informe o horario de funcionamento")
    return raw


def _has_enabled_operating_hours(values: list[schemas.OperatingHoursDay]) -> bool:
    for item in values:
        if not item.enabled:
            continue
        if item.open and item.close:
            return True
    return False


def _parse_signup_payload(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _first_non_empty(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        cleaned = str(value).strip()
        if cleaned:
            return cleaned
    return None


def _store_has_address(store: models.Store | None) -> bool:
    if store is None:
        return False
    return bool(
        _normalize_optional_text(store.postal_code)
        and _normalize_optional_text(store.street)
        and _normalize_optional_text(store.number)
        and _normalize_optional_text(store.district)
        and _normalize_optional_text(store.city)
        and _normalize_optional_text(store.state)
    )


def _store_has_operating_hours(store: models.Store | None) -> bool:
    if store is None:
        return False
    values = load_store_operating_hours(store.operating_hours)
    for item in values:
        if item.get("enabled") and item.get("open") and item.get("close"):
            return True
    return False


def _needs_onboarding(tenant: models.Tenant, store: models.Store | None) -> bool:
    activation_mode = (tenant.activation_mode or "").strip().lower()
    if activation_mode == ONBOARDING_FORCE_TEST_MODE:
        return True
    origin = (tenant.onboarding_origin or "").strip().lower()
    if origin not in ONBOARDING_REQUIRED_ORIGINS:
        return False
    if store is None:
        return True
    if not _normalize_optional_text(store.name):
        return True
    if not _normalize_optional_text(tenant.document):
        return True
    if not _normalize_optional_text(tenant.contact_email):
        return True
    if not _normalize_optional_text(tenant.contact_phone):
        return True
    if not _store_has_address(store):
        return True
    if not _store_has_operating_hours(store):
        return True
    return False


async def _resolve_store_coordinates(
    *,
    store: models.Store | None,
    postal_code: str,
    street: str,
    number: str,
    district: str,
    city: str,
    state: str,
) -> tuple[float, float]:
    fallback = (
        float(getattr(store, "lat", ONBOARDING_DEFAULT_LAT)) if store is not None else ONBOARDING_DEFAULT_LAT,
        float(getattr(store, "lon", ONBOARDING_DEFAULT_LON)) if store is not None else ONBOARDING_DEFAULT_LON,
    )
    full_address = ", ".join(
        [
            f"{street}, {number}",
            district,
            f"{city}-{state}",
            postal_code,
            "Brasil",
        ]
    )
    full_geo = await _geocode_with_nominatim(full_address)
    if full_geo is not None:
        return float(full_geo[0]), float(full_geo[1])

    postal_geo = await _geocode_with_nominatim(f"{postal_code}, Brasil")
    if postal_geo is not None:
        return float(postal_geo[0]), float(postal_geo[1])

    return fallback


def get_onboarding_state(
    db: Session,
    tenant_id: str,
    user: models.User,
) -> schemas.OnboardingStateOut:
    tenant_model = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if tenant_model is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")

    accessible_store_ids = user_accessible_store_ids(db=db, tenant_id=tenant_id, user=user)
    store: models.Store | None = None
    if accessible_store_ids:
        store = (
            db.query(models.Store)
            .filter(models.Store.tenant_id == tenant_id, models.Store.id.in_(accessible_store_ids))
            .order_by(models.Store.name.asc())
            .first()
        )

    signup_payload = _parse_signup_payload(getattr(tenant_model, "signup_payload_json", None))
    payload_email = _first_non_empty(
        signup_payload.get("contact_email"),
        signup_payload.get("email"),
        signup_payload.get("financial_contact_email"),
    )
    payload_phone = normalize_phone(
        _first_non_empty(
            signup_payload.get("contact_phone"),
            signup_payload.get("phone"),
            signup_payload.get("financial_contact_phone"),
            signup_payload.get("whatsapp"),
        )
    )

    contact_email = (
        _normalize_optional_text(tenant_model.contact_email)
        or _normalize_optional_text(payload_email)
        or _normalize_optional_text(user.email)
        or ""
    )
    contact_phone = (
        _normalize_optional_text(tenant_model.contact_phone)
        or _normalize_optional_text(payload_phone)
        or _normalize_optional_text(getattr(store, "phone", None))
        or ""
    )
    person_type = (
        tenant_model.person_type.value if tenant_model.person_type else models.CustomerPersonType.company.value
    )
    operating_hours = [
        schemas.OperatingHoursDay(**item) for item in load_store_operating_hours(getattr(store, "operating_hours", None))
    ]
    needs_onboarding = _needs_onboarding(tenant_model, store)

    return schemas.OnboardingStateOut(
        needs_onboarding=needs_onboarding,
        store_id=getattr(store, "id", None),
        store_name=(
            _normalize_optional_text(getattr(store, "name", None))
            or _normalize_optional_text(tenant_model.trade_name)
            or _normalize_optional_text(tenant_model.name)
            or ""
        ),
        person_type=person_type,
        document=_normalize_optional_text(tenant_model.document) or "",
        contact_email=contact_email,
        contact_phone=contact_phone,
        address=schemas.OnboardingAddressOut(
            postal_code=(
                _normalize_optional_text(getattr(store, "postal_code", None))
                or _normalize_optional_text(tenant_model.billing_postal_code)
                or ""
            ),
            street=(
                _normalize_optional_text(getattr(store, "street", None))
                or _normalize_optional_text(tenant_model.billing_street)
                or ""
            ),
            number=(
                _normalize_optional_text(getattr(store, "number", None))
                or _normalize_optional_text(tenant_model.billing_number)
                or ""
            ),
            district=(
                _normalize_optional_text(getattr(store, "district", None))
                or _normalize_optional_text(tenant_model.billing_district)
                or ""
            ),
            city=(
                _normalize_optional_text(getattr(store, "city", None))
                or _normalize_optional_text(tenant_model.billing_city)
                or ""
            ),
            state=(
                _normalize_optional_text(getattr(store, "state", None))
                or _normalize_optional_text(tenant_model.billing_state)
                or ""
            ),
            complement=(
                _normalize_optional_text(getattr(store, "complement", None))
                or _normalize_optional_text(tenant_model.billing_complement)
                or ""
            ),
            reference=_normalize_optional_text(getattr(store, "reference", None)) or "",
        ),
        operating_hours=operating_hours,
    )


async def complete_onboarding(
    db: Session,
    tenant_id: str,
    tenant_slug: str,
    stores_limit: int | None,
    user: models.User,
    payload: schemas.OnboardingCompletePayload,
) -> schemas.OnboardingCompleteOut:
    tenant_model = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if tenant_model is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")

    accessible_store_ids = set(user_accessible_store_ids(db=db, tenant_id=tenant_id, user=user))
    store: models.Store | None = None
    if payload.store_id:
        if payload.store_id not in accessible_store_ids:
            raise HTTPException(status_code=403, detail="Store access denied")
        store = (
            db.query(models.Store)
            .filter(models.Store.id == payload.store_id, models.Store.tenant_id == tenant_id)
            .first()
        )
        if store is None:
            raise HTTPException(status_code=404, detail="Store not found")
    elif accessible_store_ids:
        store = (
            db.query(models.Store)
            .filter(models.Store.tenant_id == tenant_id, models.Store.id.in_(list(accessible_store_ids)))
            .order_by(models.Store.name.asc())
            .first()
        )

    person_type = _normalize_person_type(payload.person_type)
    document = _normalize_document(payload.document)
    _validate_document(person_type, document)

    contact_email = _normalize_optional_text(str(payload.contact_email))
    if not contact_email:
        raise HTTPException(status_code=400, detail="Email obrigatorio")

    contact_phone = normalize_phone(payload.contact_phone)
    if not contact_phone:
        raise HTTPException(status_code=400, detail="Telefone invalido")

    store_name = _normalize_optional_text(payload.store_name)
    if not store_name:
        raise HTTPException(status_code=400, detail="Nome da loja obrigatorio")

    postal_code = _normalize_postal_code(payload.postal_code)
    street = _normalize_optional_text(payload.street)
    number = _normalize_optional_text(payload.number)
    district = _normalize_optional_text(payload.district)
    city = _normalize_optional_text(payload.city)
    state = _normalize_state(payload.state)
    if not street or not number or not district or not city:
        raise HTTPException(status_code=400, detail="Endereco incompleto")

    if not payload.operating_hours or not _has_enabled_operating_hours(payload.operating_hours):
        raise HTTPException(status_code=400, detail="Informe ao menos um horario de funcionamento")
    operating_hours_raw = _dump_operating_hours(payload.operating_hours)

    lat, lon = await _resolve_store_coordinates(
        store=store,
        postal_code=postal_code,
        street=street,
        number=number,
        district=district,
        city=city,
        state=state,
    )

    if store is None:
        if stores_limit is not None:
            used = db.query(models.Store.id).filter(models.Store.tenant_id == tenant_id).count()
            if used >= stores_limit:
                raise HTTPException(status_code=400, detail="Limite de lojas atingido para este tenant")
        store = models.Store(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=store_name,
            slug=ensure_unique_store_slug(db, tenant_id, store_name),
            lat=lat,
            lon=lon,
            timezone=DEFAULT_STORE_TIMEZONE,
            is_active=True,
            is_delivery=True,
            allow_preorder_when_closed=True,
        )
        db.add(store)
    else:
        store.name = store_name
        store.slug = ensure_unique_store_slug(db, tenant_id, store_name, exclude_store_id=store.id)

    store.lat = lat
    store.lon = lon
    store.timezone = (store.timezone or DEFAULT_STORE_TIMEZONE).strip() or DEFAULT_STORE_TIMEZONE
    store.postal_code = postal_code
    store.street = street
    store.number = number
    store.district = district
    store.city = city
    store.state = state
    store.complement = _normalize_optional_text(payload.complement)
    store.reference = _normalize_optional_text(payload.reference)
    store.phone = contact_phone
    store.operating_hours = operating_hours_raw

    tenant_model.person_type = person_type
    tenant_model.document = document
    tenant_model.contact_email = contact_email
    tenant_model.contact_phone = contact_phone
    tenant_model.trade_name = _normalize_optional_text(tenant_model.trade_name) or store_name
    tenant_model.billing_postal_code = postal_code
    tenant_model.billing_street = street
    tenant_model.billing_number = number
    tenant_model.billing_district = district
    tenant_model.billing_city = city
    tenant_model.billing_state = state
    tenant_model.billing_complement = _normalize_optional_text(payload.complement)
    if (tenant_model.activation_mode or "").strip().lower() == ONBOARDING_FORCE_TEST_MODE:
        tenant_model.activation_mode = "manual"

    db.commit()
    db.refresh(store)
    return schemas.OnboardingCompleteOut(ok=True, store_id=store.id)


def enable_onboarding_test_mode(db: Session, tenant_id: str) -> schemas.OnboardingTestModeOut:
    tenant_model = db.query(models.Tenant).filter(models.Tenant.id == tenant_id).first()
    if tenant_model is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    tenant_model.activation_mode = ONBOARDING_FORCE_TEST_MODE
    db.commit()
    return schemas.OnboardingTestModeOut(ok=True, activation_mode=tenant_model.activation_mode or "manual")
