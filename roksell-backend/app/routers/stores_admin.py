import json
import uuid
import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app import models, schemas
from app.domain.config.order_statuses import (
    load_order_final_statuses,
    load_order_status_colors,
    load_order_statuses,
    normalize_order_final_statuses,
    normalize_order_status_colors,
    normalize_order_statuses,
)
from app.domain.config.payment_methods import load_payment_methods, normalize_payment_methods
from app.domain.config.shipping_method import load_shipping_method, normalize_shipping_method
from app.domain.shipping.store_calendar import dump_store_closed_dates, load_store_closed_dates
from app.domain.shipping.store_hours import dump_store_operating_hours, load_store_operating_hours
from app.domain.shipping.store_timezone import DEFAULT_STORE_TIMEZONE, normalize_store_timezone
from app.domain.tenancy.access import ensure_unique_store_slug, user_accessible_store_ids
from app.auth.dependencies import require_module, require_roles
from app.db import get_db
from app.phone import normalize_phone
from app.storage import build_media_key, storage_delete_by_url, storage_save
from app.tenancy import TenantContext

router = APIRouter(prefix="/admin/stores", tags=["admin-stores"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xFF\xD8\xFF"
RIFF_SIGNATURE = b"RIFF"
WEBP_SIGNATURE = b"WEBP"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_postal_code(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D+", "", value)
    if not digits:
        return None
    if len(digits) != 8:
        raise HTTPException(status_code=422, detail="postal_code must have 8 digits")
    return digits


def _store_out_payload(store: models.Store) -> dict:
    order_statuses = load_order_statuses(getattr(store, "order_statuses", None))
    return {
        "id": store.id,
        "name": store.name,
        "slug": store.slug,
        "timezone": (store.timezone or DEFAULT_STORE_TIMEZONE),
        "is_active": store.is_active,
        "is_delivery": store.is_delivery,
        "allow_preorder_when_closed": bool(getattr(store, "allow_preorder_when_closed", True)),
        "lat": float(store.lat),
        "lon": float(store.lon),
        "closed_dates": load_store_closed_dates(store.closed_dates),
        "operating_hours": load_store_operating_hours(store.operating_hours),
        "postal_code": store.postal_code,
        "street": store.street,
        "number": store.number,
        "district": store.district,
        "city": store.city,
        "state": store.state,
        "complement": store.complement,
        "reference": store.reference,
        "phone": store.phone,
        "sla_minutes": int(getattr(store, "sla_minutes", 45) or 45),
        "cover_image_url": getattr(store, "cover_image_url", None),
        "whatsapp_contact_phone": getattr(store, "whatsapp_contact_phone", None),
        "payment_methods": load_payment_methods(getattr(store, "payment_methods", None)),
        "order_statuses": order_statuses,
        "order_status_canceled_color": getattr(store, "order_status_canceled_color", None),
        "order_status_colors": load_order_status_colors(getattr(store, "order_status_colors", None), order_statuses),
        "order_final_statuses": load_order_final_statuses(getattr(store, "order_final_statuses", None), order_statuses),
        "shipping_method": load_shipping_method(getattr(store, "shipping_method", None)),
        "shipping_fixed_fee_cents": int(getattr(store, "shipping_fixed_fee_cents", 0) or 0),
    }


def _get_store(db: Session, tenant_id: str, store_id: str) -> models.Store | None:
    return (
        db.query(models.Store)
        .filter(models.Store.id == store_id, models.Store.tenant_id == tenant_id)
        .first()
    )


def _dump_operating_hours(payload: schemas.StoreCreate | schemas.StoreUpdate) -> str | None:
    if payload.operating_hours is None:
        return None
    try:
        return dump_store_operating_hours([item.dict() for item in payload.operating_hours])
    except ValueError:
        raise HTTPException(status_code=400, detail="Horario de funcionamento invalido")


def _normalize_timezone_or_400(value: str | None) -> str:
    try:
        return normalize_store_timezone(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Timezone invalida")


def _apply_store_settings_payload(
    *,
    store: models.Store,
    payload: schemas.StoreCreate | schemas.StoreUpdate,
) -> None:
    if payload.phone is not None:
        cleaned_phone = _normalize_optional_text(payload.phone)
        store.phone = normalize_phone(cleaned_phone) if cleaned_phone else None
    if payload.sla_minutes is not None:
        store.sla_minutes = int(payload.sla_minutes)
    if payload.cover_image_url is not None:
        normalized_cover = _normalize_optional_text(payload.cover_image_url)
        if not normalized_cover and store.cover_image_url:
            storage_delete_by_url(store.cover_image_url)
        store.cover_image_url = normalized_cover
    if payload.whatsapp_contact_phone is not None:
        cleaned_contact = _normalize_optional_text(payload.whatsapp_contact_phone)
        store.whatsapp_contact_phone = normalize_phone(cleaned_contact) if cleaned_contact else None
    if payload.payment_methods is not None:
        try:
            normalized_methods = normalize_payment_methods(payload.payment_methods)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        store.payment_methods = json.dumps(normalized_methods)
    normalized_statuses: list[str] | None = None
    if payload.order_statuses is not None:
        try:
            normalized_statuses = normalize_order_statuses(payload.order_statuses)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        store.order_statuses = json.dumps(normalized_statuses)
    if payload.order_final_statuses is not None:
        statuses_for_final = normalized_statuses or load_order_statuses(store.order_statuses)
        normalized_final = normalize_order_final_statuses(payload.order_final_statuses, statuses_for_final)
        store.order_final_statuses = json.dumps(normalized_final)
    if payload.order_status_canceled_color is not None:
        store.order_status_canceled_color = _normalize_optional_text(payload.order_status_canceled_color)
    if payload.order_status_colors is not None:
        try:
            statuses_for_colors = normalized_statuses or load_order_statuses(store.order_statuses)
            normalized_colors = normalize_order_status_colors(payload.order_status_colors, statuses_for_colors)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        store.order_status_colors = json.dumps(normalized_colors)
        if "canceled" in normalized_colors:
            store.order_status_canceled_color = normalized_colors["canceled"]
    if payload.shipping_method is not None:
        try:
            store.shipping_method = normalize_shipping_method(payload.shipping_method)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload.shipping_fixed_fee_cents is not None:
        fixed_fee = int(payload.shipping_fixed_fee_cents)
        if fixed_fee < 0:
            raise HTTPException(status_code=400, detail="shipping_fixed_fee_cents must be >= 0")
        store.shipping_fixed_fee_cents = fixed_fee


@router.get("", response_model=list[schemas.StoreOut])
def list_stores(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("stores")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    accessible_store_ids = user_accessible_store_ids(db=db, tenant_id=tenant.id, user=user)
    stores = (
        db.query(models.Store)
        .filter(models.Store.tenant_id == tenant.id, models.Store.id.in_(accessible_store_ids))
        .order_by(models.Store.name.asc())
        .all()
    )
    return [_store_out_payload(store) for store in stores]


@router.post("", response_model=schemas.StoreOut, status_code=201)
def create_store(
    payload: schemas.StoreCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("stores")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    if tenant.stores_limit is not None:
        used = (
            db.query(models.Store.id)
            .filter(models.Store.tenant_id == tenant.id)
            .count()
        )
        if used >= tenant.stores_limit:
            raise HTTPException(status_code=400, detail="Limite de lojas atingido para este tenant")
    store = models.Store(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        name=payload.name.strip(),
        slug=ensure_unique_store_slug(db, tenant.id, payload.name),
        lat=payload.lat,
        lon=payload.lon,
        timezone=_normalize_timezone_or_400(payload.timezone),
        closed_dates=dump_store_closed_dates(payload.closed_dates),
        operating_hours=_dump_operating_hours(payload),
        postal_code=_normalize_postal_code(payload.postal_code),
        street=payload.street,
        number=payload.number,
        district=payload.district,
        city=payload.city,
        state=payload.state,
        complement=payload.complement,
        reference=payload.reference,
        is_delivery=payload.is_delivery,
        allow_preorder_when_closed=payload.allow_preorder_when_closed,
        is_active=payload.is_active,
    )
    _apply_store_settings_payload(store=store, payload=payload)
    db.add(store)
    db.commit()
    db.refresh(store)
    return _store_out_payload(store)


@router.patch("/{store_id}", response_model=schemas.StoreOut)
def update_store(
    store_id: str,
    payload: schemas.StoreUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("stores")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    allowed_store_ids = user_accessible_store_ids(db=db, tenant_id=tenant.id, user=user)
    if store_id not in allowed_store_ids:
        raise HTTPException(status_code=403, detail="Store access denied")

    store = _get_store(db, tenant.id, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    if payload.name is not None:
        store.name = payload.name.strip()
        store.slug = ensure_unique_store_slug(db, tenant.id, payload.name, exclude_store_id=store.id)
    if payload.lat is not None:
        store.lat = payload.lat
    if payload.lon is not None:
        store.lon = payload.lon
    if payload.timezone is not None:
        store.timezone = _normalize_timezone_or_400(payload.timezone)
    if payload.closed_dates is not None:
        store.closed_dates = dump_store_closed_dates(payload.closed_dates)
    if payload.operating_hours is not None:
        store.operating_hours = _dump_operating_hours(payload)
    if payload.postal_code is not None:
        store.postal_code = _normalize_postal_code(payload.postal_code)
    if payload.street is not None:
        store.street = payload.street
    if payload.number is not None:
        store.number = payload.number
    if payload.district is not None:
        store.district = payload.district
    if payload.city is not None:
        store.city = payload.city
    if payload.state is not None:
        store.state = payload.state
    if payload.complement is not None:
        store.complement = payload.complement
    if payload.reference is not None:
        store.reference = payload.reference
    if payload.is_delivery is not None:
        store.is_delivery = payload.is_delivery
    if payload.allow_preorder_when_closed is not None:
        store.allow_preorder_when_closed = payload.allow_preorder_when_closed
    if payload.is_active is not None:
        store.is_active = payload.is_active
    _apply_store_settings_payload(store=store, payload=payload)

    db.commit()
    db.refresh(store)
    return _store_out_payload(store)


def _get_store_with_access_or_404(
    *,
    db: Session,
    tenant_id: str,
    user: models.User,
    store_id: str,
) -> models.Store:
    allowed_store_ids = user_accessible_store_ids(db=db, tenant_id=tenant_id, user=user)
    if store_id not in allowed_store_ids:
        raise HTTPException(status_code=403, detail="Store access denied")
    store = _get_store(db, tenant_id, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.post("/{store_id}/cover", response_model=schemas.StoreOut)
def upload_store_cover(
    store_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("stores")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    store = _get_store_with_access_or_404(db=db, tenant_id=tenant.id, user=user, store_id=store_id)
    expected_ext = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if not expected_ext:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    contents = file.file.read(MAX_IMAGE_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image file")
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    detected_ext = None
    if contents.startswith(PNG_SIGNATURE):
        detected_ext = "png"
    elif contents.startswith(JPEG_SIGNATURE):
        detected_ext = "jpg"
    elif contents.startswith(RIFF_SIGNATURE) and contents[8:12] == WEBP_SIGNATURE:
        detected_ext = "webp"
    if detected_ext != expected_ext:
        raise HTTPException(status_code=400, detail="Invalid image file")

    filename = f"{uuid.uuid4()}.{detected_ext}"
    key = build_media_key("tenants", tenant.slug, "stores", store.id, "cover", filename)
    storage_delete_by_url(store.cover_image_url)
    store.cover_image_url = storage_save(key, contents, file.content_type)
    db.commit()
    db.refresh(store)
    return _store_out_payload(store)


@router.delete("/{store_id}/cover", response_model=schemas.StoreOut)
def remove_store_cover(
    store_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("stores")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    store = _get_store_with_access_or_404(db=db, tenant_id=tenant.id, user=user, store_id=store_id)
    storage_delete_by_url(store.cover_image_url)
    store.cover_image_url = None
    db.commit()
    db.refresh(store)
    return _store_out_payload(store)
