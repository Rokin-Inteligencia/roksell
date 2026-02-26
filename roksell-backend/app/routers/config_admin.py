import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import require_module, require_roles
from app.db import get_db
from app.domain.config.operating_hours import load_operating_hours, normalize_operating_hours
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
from app.tenancy import TenantContext
from app.phone import normalize_phone
from app.storage import build_media_key, storage_delete_by_url, storage_save

router = APIRouter(prefix="/admin/config", tags=["admin-config"])

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


def _get_or_create_config(db: Session, tenant_id: str) -> models.OperationsConfig:
    cfg = (
        db.query(models.OperationsConfig)
        .filter(models.OperationsConfig.tenant_id == tenant_id)
        .first()
    )
    if not cfg:
        cfg = models.OperationsConfig(tenant_id=tenant_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("", response_model=schemas.OperationsConfigUpdate)
def get_config(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("config")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    cfg = _get_or_create_config(db, tenant.id)
    order_statuses = load_order_statuses(cfg.order_statuses)
    return schemas.OperationsConfigUpdate(
        sla_minutes=cfg.sla_minutes,
        delivery_enabled=cfg.delivery_enabled,
        cover_image_url=cfg.cover_image_url,
        whatsapp_contact_phone=cfg.whatsapp_contact_phone,
        whatsapp_order_message=cfg.whatsapp_order_message,
        whatsapp_status_message=cfg.whatsapp_status_message,
        pix_key=cfg.pix_key,
        order_statuses=order_statuses,
        order_final_statuses=load_order_final_statuses(cfg.order_final_statuses, order_statuses),
        order_status_canceled_color=cfg.order_status_canceled_color,
        order_status_colors=load_order_status_colors(cfg.order_status_colors, order_statuses),
        operating_hours=load_operating_hours(cfg.operating_hours),
        payment_methods=load_payment_methods(cfg.payment_methods),
        shipping_method=load_shipping_method(cfg.shipping_method),
    )


@router.patch("", response_model=schemas.OperationsConfigUpdate)
def update_config(
    payload: schemas.OperationsConfigUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("config")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    cfg = _get_or_create_config(db, tenant.id)
    if payload.sla_minutes is not None:
        cfg.sla_minutes = payload.sla_minutes
    if payload.delivery_enabled is not None:
        cfg.delivery_enabled = payload.delivery_enabled
    if payload.cover_image_url is not None:
        normalized = _normalize_optional_text(payload.cover_image_url)
        if not normalized and cfg.cover_image_url:
            storage_delete_by_url(cfg.cover_image_url)
        cfg.cover_image_url = normalized
    if payload.whatsapp_contact_phone is not None:
        cleaned = _normalize_optional_text(payload.whatsapp_contact_phone)
        cfg.whatsapp_contact_phone = normalize_phone(cleaned) if cleaned else None
    if payload.whatsapp_order_message is not None:
        cfg.whatsapp_order_message = _normalize_optional_text(payload.whatsapp_order_message)
    if payload.whatsapp_status_message is not None:
        cfg.whatsapp_status_message = _normalize_optional_text(payload.whatsapp_status_message)
    if payload.pix_key is not None:
        cfg.pix_key = _normalize_optional_text(payload.pix_key)
    normalized_statuses: list[str] | None = None
    if payload.order_statuses is not None:
        try:
            normalized_statuses = normalize_order_statuses(payload.order_statuses)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        cfg.order_statuses = json.dumps(normalized_statuses)
    if payload.order_final_statuses is not None:
        statuses_for_final = normalized_statuses or load_order_statuses(cfg.order_statuses)
        normalized_final = normalize_order_final_statuses(payload.order_final_statuses, statuses_for_final)
        cfg.order_final_statuses = json.dumps(normalized_final)
    if payload.order_status_canceled_color is not None:
        cfg.order_status_canceled_color = _normalize_optional_text(payload.order_status_canceled_color)
    if payload.order_status_colors is not None:
        try:
            statuses_for_colors = normalized_statuses or load_order_statuses(cfg.order_statuses)
            normalized_colors = normalize_order_status_colors(payload.order_status_colors, statuses_for_colors)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        cfg.order_status_colors = json.dumps(normalized_colors)
        if "canceled" in normalized_colors:
            cfg.order_status_canceled_color = normalized_colors["canceled"]
    if payload.operating_hours is not None:
        try:
            normalized_hours = normalize_operating_hours([item.dict() for item in payload.operating_hours])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        cfg.operating_hours = json.dumps(normalized_hours)
    if payload.payment_methods is not None:
        try:
            normalized_methods = normalize_payment_methods(payload.payment_methods)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        cfg.payment_methods = json.dumps(normalized_methods)
    if payload.shipping_method is not None:
        try:
            cfg.shipping_method = normalize_shipping_method(payload.shipping_method)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    order_statuses = load_order_statuses(cfg.order_statuses)
    return schemas.OperationsConfigUpdate(
        sla_minutes=cfg.sla_minutes,
        delivery_enabled=cfg.delivery_enabled,
        cover_image_url=cfg.cover_image_url,
        whatsapp_contact_phone=cfg.whatsapp_contact_phone,
        whatsapp_order_message=cfg.whatsapp_order_message,
        whatsapp_status_message=cfg.whatsapp_status_message,
        pix_key=cfg.pix_key,
        order_statuses=order_statuses,
        order_final_statuses=load_order_final_statuses(cfg.order_final_statuses, order_statuses),
        order_status_canceled_color=cfg.order_status_canceled_color,
        order_status_colors=load_order_status_colors(cfg.order_status_colors, order_statuses),
        operating_hours=load_operating_hours(cfg.operating_hours),
        payment_methods=load_payment_methods(cfg.payment_methods),
        shipping_method=load_shipping_method(cfg.shipping_method),
    )


@router.post("/cover", response_model=schemas.OperationsConfigUpdate)
def upload_cover(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("config")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    cfg = _get_or_create_config(db, tenant.id)
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
    key = build_media_key("tenants", tenant.slug, "vitrine", "cover", filename)
    storage_delete_by_url(cfg.cover_image_url)
    cfg.cover_image_url = storage_save(key, contents, file.content_type)
    db.commit()
    db.refresh(cfg)
    order_statuses = load_order_statuses(cfg.order_statuses)
    return schemas.OperationsConfigUpdate(
        sla_minutes=cfg.sla_minutes,
        delivery_enabled=cfg.delivery_enabled,
        cover_image_url=cfg.cover_image_url,
        whatsapp_contact_phone=cfg.whatsapp_contact_phone,
        whatsapp_order_message=cfg.whatsapp_order_message,
        whatsapp_status_message=cfg.whatsapp_status_message,
        pix_key=cfg.pix_key,
        order_statuses=order_statuses,
        order_final_statuses=load_order_final_statuses(cfg.order_final_statuses, order_statuses),
        order_status_canceled_color=cfg.order_status_canceled_color,
        order_status_colors=load_order_status_colors(cfg.order_status_colors, order_statuses),
        operating_hours=load_operating_hours(cfg.operating_hours),
        payment_methods=load_payment_methods(cfg.payment_methods),
        shipping_method=load_shipping_method(cfg.shipping_method),
    )


@router.delete("/cover", response_model=schemas.OperationsConfigUpdate)
def remove_cover(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("config")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    cfg = _get_or_create_config(db, tenant.id)
    storage_delete_by_url(cfg.cover_image_url)
    cfg.cover_image_url = None
    db.commit()
    order_statuses = load_order_statuses(cfg.order_statuses)
    return schemas.OperationsConfigUpdate(
        sla_minutes=cfg.sla_minutes,
        delivery_enabled=cfg.delivery_enabled,
        cover_image_url=cfg.cover_image_url,
        whatsapp_contact_phone=cfg.whatsapp_contact_phone,
        whatsapp_order_message=cfg.whatsapp_order_message,
        whatsapp_status_message=cfg.whatsapp_status_message,
        pix_key=cfg.pix_key,
        order_statuses=order_statuses,
        order_final_statuses=load_order_final_statuses(cfg.order_final_statuses, order_statuses),
        order_status_canceled_color=cfg.order_status_canceled_color,
        order_status_colors=load_order_status_colors(cfg.order_status_colors, order_statuses),
        operating_hours=load_operating_hours(cfg.operating_hours),
        payment_methods=load_payment_methods(cfg.payment_methods),
        shipping_method=load_shipping_method(cfg.shipping_method),
    )
