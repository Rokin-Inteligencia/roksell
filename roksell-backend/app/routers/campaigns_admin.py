import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import require_module_action, require_roles
from app.db import get_db
from app.domain.core.enums import CampaignType
from app.domain.tenancy.access import user_accessible_store_ids
from app.tenancy import TenantContext
from app.storage import build_media_key, storage_delete_by_url, storage_save

router = APIRouter(prefix="/admin/campaigns", tags=["admin-campaigns"])
_VALID_BANNER_POSITIONS = {"top", "between"}
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


def _normalize_coupon(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    cleaned = code.strip()
    return cleaned.upper() or None


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _validate_dates(starts_at: Optional[datetime], ends_at: Optional[datetime]) -> None:
    if starts_at and starts_at.tzinfo is None:
        raise HTTPException(400, "starts_at must be timezone-aware")
    if ends_at and ends_at.tzinfo is None:
        raise HTTPException(400, "ends_at must be timezone-aware")
    if starts_at and ends_at and ends_at < starts_at:
        raise HTTPException(400, "ends_at must be after starts_at")


def _coerce_type(value: str | None) -> CampaignType:
    if not value:
        raise HTTPException(400, "type is required")
    try:
        return CampaignType(value)
    except ValueError:
        raise HTTPException(400, "Invalid campaign type")


def _normalize_apply_mode(value: Optional[str]) -> str:
    if not value:
        return "first"
    cleaned = value.strip().lower()
    if cleaned not in {"first", "stack"}:
        raise HTTPException(400, "Invalid apply_mode")
    return cleaned


def _normalize_priority(value: Optional[int]) -> int:
    if value is None:
        return 0
    return int(value)


def _normalize_rule_config(value: Optional[dict]) -> Optional[dict]:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise HTTPException(400, "rule_config must be an object")
    return value


def _validate_rule_config(rule_config: dict) -> None:
    rules = rule_config.get("rules")
    if not isinstance(rules, list) or not rules:
        raise HTTPException(400, "rule_config.rules must be a non-empty list")
    for idx, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            raise HTTPException(400, f"rule {idx} must be an object")
        conditions = rule.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            raise HTTPException(400, f"rule {idx} must have conditions")
        action = rule.get("action")
        if not isinstance(action, dict) or not action.get("type"):
            raise HTTPException(400, f"rule {idx} must have action.type")


def _load_store_ids(
    db: Session,
    tenant_id: str,
    store_ids: Optional[list[str]],
    allowed_store_ids: Optional[list[str]] = None,
) -> list[str]:
    if not store_ids:
        return []
    normalized = [s for s in store_ids if s]
    if not normalized:
        return []
    rows = (
        db.query(models.Store.id)
        .filter(models.Store.tenant_id == tenant_id, models.Store.id.in_(normalized))
        .all()
    )
    valid = {r[0] for r in rows}
    invalid = [s for s in normalized if s not in valid]
    if invalid:
        raise HTTPException(400, "store_ids contains invalid store")
    if allowed_store_ids is not None:
        out_of_scope = [s for s in normalized if s not in set(allowed_store_ids)]
        if out_of_scope:
            raise HTTPException(403, "store_ids contains store without access")
    return normalized


def _campaign_out_payload(db: Session, tenant_id: str, campaign: models.Campaign) -> dict:
    store_rows = (
        db.query(models.CampaignStore.store_id)
        .filter(
            models.CampaignStore.tenant_id == tenant_id,
            models.CampaignStore.campaign_id == campaign.id,
        )
        .all()
    )
    store_ids = [r[0] for r in store_rows]
    rule_config = None
    if campaign.rule_config:
        try:
            rule_config = json.loads(campaign.rule_config)
        except json.JSONDecodeError:
            rule_config = None
    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "type": campaign.type.value if hasattr(campaign.type, "value") else str(campaign.type),
        "value_percent": campaign.value_percent,
        "coupon_code": campaign.coupon_code,
        "category_id": campaign.category_id,
        "min_order_cents": campaign.min_order_cents,
        "starts_at": campaign.starts_at,
        "ends_at": campaign.ends_at,
        "is_active": campaign.is_active,
        "usage_limit": campaign.usage_limit,
        "usage_count": campaign.usage_count,
        "apply_mode": campaign.apply_mode,
        "priority": campaign.priority,
        "rule_config": rule_config,
        "store_ids": store_ids,
        "banner_enabled": campaign.banner_enabled,
        "banner_position": campaign.banner_position,
        "banner_popup": campaign.banner_popup,
        "banner_image_url": campaign.banner_image_url,
        "banner_link_url": campaign.banner_link_url,
        "created_at": campaign.created_at,
    }


def _normalize_banner_position(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned not in _VALID_BANNER_POSITIONS:
        raise HTTPException(400, "Invalid banner_position")
    return cleaned


@router.get("", response_model=list[schemas.CampaignOut])
def list_campaigns(
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    search: str | None = Query(None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("campaigns", "view")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    offset = (page - 1) * limit
    query = db.query(models.Campaign).filter(models.Campaign.tenant_id == tenant.id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(models.Campaign.name.ilike(term), models.Campaign.coupon_code.ilike(term))
        )
    campaigns = query.order_by(models.Campaign.created_at.desc()).offset(offset).limit(limit).all()
    return [_campaign_out_payload(db, tenant.id, campaign) for campaign in campaigns]


@router.post("", response_model=schemas.CampaignOut)
def create_campaign(
    payload: schemas.CampaignCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("campaigns", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    ctype = _coerce_type(payload.type)
    coupon_code = _normalize_coupon(payload.coupon_code)
    _validate_dates(payload.starts_at, payload.ends_at)

    if payload.value_percent < 0 or payload.value_percent > 100:
        raise HTTPException(400, "value_percent must be between 0 and 100")
    if payload.usage_limit is not None and payload.usage_limit < 1:
        raise HTTPException(400, "usage_limit must be positive")
    if not payload.name.strip():
        raise HTTPException(400, "name is required")

    category_id = payload.category_id
    if ctype == CampaignType.category_percent:
        if not category_id:
            raise HTTPException(400, "category_id is required for category_percent")
        exists = (
            db.query(models.Category)
            .filter(models.Category.id == category_id, models.Category.tenant_id == tenant.id)
            .first()
        )
        if not exists:
            raise HTTPException(400, "category not found for tenant")
    else:
        category_id = None

    rule_config = _normalize_rule_config(payload.rule_config)
    if ctype == CampaignType.rule:
        if not rule_config:
            raise HTTPException(400, "rule_config is required for rule campaigns")
        _validate_rule_config(rule_config)
    else:
        rule_config = None

    apply_mode = _normalize_apply_mode(payload.apply_mode)
    priority = _normalize_priority(payload.priority)
    allowed_store_ids = user_accessible_store_ids(db=db, tenant_id=tenant.id, user=user)
    store_ids = _load_store_ids(db, tenant.id, payload.store_ids, allowed_store_ids=allowed_store_ids)

    banner_enabled = payload.banner_enabled
    banner_image_url = _normalize_optional_text(payload.banner_image_url)
    banner_link_url = _normalize_optional_text(payload.banner_link_url)
    banner_position = _normalize_banner_position(payload.banner_position)
    banner_popup = payload.banner_popup
    if banner_enabled:
        if not banner_image_url:
            raise HTTPException(400, "banner_image_url is required when banner_enabled")
        if not banner_position:
            banner_position = "top"
    else:
        banner_popup = False
        banner_position = None

    campaign = models.Campaign(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        name=payload.name.strip(),
        type=ctype,
        value_percent=payload.value_percent,
        coupon_code=coupon_code,
        category_id=category_id,
        min_order_cents=payload.min_order_cents,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=payload.is_active,
        usage_limit=payload.usage_limit,
        usage_count=0,
        banner_enabled=banner_enabled,
        banner_position=banner_position,
        banner_popup=banner_popup,
        banner_image_url=banner_image_url,
        banner_link_url=banner_link_url,
        rule_config=json.dumps(rule_config) if rule_config else None,
        apply_mode=apply_mode,
        priority=priority,
    )
    db.add(campaign)
    db.flush()
    if store_ids:
        for store_id in store_ids:
            db.add(
                models.CampaignStore(
                    tenant_id=tenant.id,
                    campaign_id=campaign.id,
                    store_id=store_id,
                )
            )
    db.commit()
    db.refresh(campaign)
    return _campaign_out_payload(db, tenant.id, campaign)


@router.patch("/{campaign_id}", response_model=schemas.CampaignOut)
def update_campaign(
    campaign_id: str,
    payload: schemas.CampaignUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("campaigns", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    campaign = (
        db.query(models.Campaign)
        .filter(models.Campaign.id == campaign_id, models.Campaign.tenant_id == tenant.id)
        .first()
    )
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    ctype = _coerce_type(payload.type) if payload.type is not None else campaign.type
    coupon_code = _normalize_coupon(payload.coupon_code) if payload.coupon_code is not None else campaign.coupon_code
    starts_at = payload.starts_at if payload.starts_at is not None else campaign.starts_at
    ends_at = payload.ends_at if payload.ends_at is not None else campaign.ends_at
    _validate_dates(starts_at, ends_at)

    value_percent = payload.value_percent if payload.value_percent is not None else campaign.value_percent
    if value_percent < 0 or value_percent > 100:
        raise HTTPException(400, "value_percent must be between 0 and 100")

    usage_limit = payload.usage_limit if payload.usage_limit is not None else campaign.usage_limit
    if usage_limit is not None and usage_limit < 1:
        raise HTTPException(400, "usage_limit must be positive")
    if usage_limit is not None and campaign.usage_count > usage_limit:
        raise HTTPException(400, "usage_limit cannot be lower than current usage")
    if payload.name is not None and not payload.name.strip():
        raise HTTPException(400, "name is required")

    category_id = payload.category_id if payload.category_id is not None else campaign.category_id
    if ctype == CampaignType.category_percent:
        if not category_id:
            raise HTTPException(400, "category_id is required for category_percent")
        exists = (
            db.query(models.Category)
            .filter(models.Category.id == category_id, models.Category.tenant_id == tenant.id)
            .first()
        )
        if not exists:
            raise HTTPException(400, "category not found for tenant")
    else:
        category_id = None

    rule_config = campaign.rule_config
    if payload.rule_config is not None:
        normalized_rule_config = _normalize_rule_config(payload.rule_config)
        if ctype == CampaignType.rule:
            if not normalized_rule_config:
                raise HTTPException(400, "rule_config is required for rule campaigns")
            _validate_rule_config(normalized_rule_config)
        else:
            normalized_rule_config = None
        rule_config = json.dumps(normalized_rule_config) if normalized_rule_config else None
    elif ctype != CampaignType.rule:
        rule_config = None

    apply_mode = (
        _normalize_apply_mode(payload.apply_mode)
        if payload.apply_mode is not None
        else campaign.apply_mode
    )
    priority = (
        _normalize_priority(payload.priority)
        if payload.priority is not None
        else campaign.priority
    )
    store_ids = None
    if payload.store_ids is not None:
        allowed_store_ids = user_accessible_store_ids(db=db, tenant_id=tenant.id, user=user)
        store_ids = _load_store_ids(db, tenant.id, payload.store_ids, allowed_store_ids=allowed_store_ids)

    banner_enabled = payload.banner_enabled if payload.banner_enabled is not None else campaign.banner_enabled
    banner_image_url_set = "banner_image_url" in payload.model_fields_set
    banner_image_url = (
        _normalize_optional_text(payload.banner_image_url)
        if banner_image_url_set
        else campaign.banner_image_url
    )
    banner_link_url = (
        _normalize_optional_text(payload.banner_link_url)
        if payload.banner_link_url is not None
        else campaign.banner_link_url
    )
    banner_position = (
        _normalize_banner_position(payload.banner_position)
        if payload.banner_position is not None
        else campaign.banner_position
    )
    banner_popup = payload.banner_popup if payload.banner_popup is not None else campaign.banner_popup
    if banner_enabled:
        if not banner_image_url:
            raise HTTPException(400, "banner_image_url is required when banner_enabled")
        if not banner_position:
            banner_position = "top"
    else:
        banner_popup = False
        banner_position = None
    if banner_image_url_set and banner_image_url != campaign.banner_image_url:
        storage_delete_by_url(campaign.banner_image_url)

    campaign.name = payload.name.strip() if payload.name is not None else campaign.name
    campaign.type = ctype
    campaign.value_percent = value_percent
    campaign.coupon_code = coupon_code
    campaign.category_id = category_id
    campaign.min_order_cents = payload.min_order_cents if payload.min_order_cents is not None else campaign.min_order_cents
    campaign.starts_at = starts_at
    campaign.ends_at = ends_at
    campaign.is_active = payload.is_active if payload.is_active is not None else campaign.is_active
    campaign.usage_limit = usage_limit
    campaign.banner_enabled = banner_enabled
    campaign.banner_position = banner_position
    campaign.banner_popup = banner_popup
    campaign.banner_image_url = banner_image_url
    campaign.banner_link_url = banner_link_url
    campaign.rule_config = rule_config
    campaign.apply_mode = apply_mode
    campaign.priority = priority
    campaign.updated_at = datetime.now(timezone.utc)

    if store_ids is not None:
        db.query(models.CampaignStore).filter(
            models.CampaignStore.tenant_id == tenant.id,
            models.CampaignStore.campaign_id == campaign.id,
        ).delete()
        for store_id in store_ids:
            db.add(
                models.CampaignStore(
                    tenant_id=tenant.id,
                    campaign_id=campaign.id,
                    store_id=store_id,
                )
            )

    db.commit()
    db.refresh(campaign)
    return _campaign_out_payload(db, tenant.id, campaign)


@router.post("/{campaign_id}/banner", response_model=schemas.CampaignOut)
def upload_campaign_banner(
    campaign_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("campaigns", "edit")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    campaign = (
        db.query(models.Campaign)
        .filter(models.Campaign.id == campaign_id, models.Campaign.tenant_id == tenant.id)
        .first()
    )
    if not campaign:
        raise HTTPException(404, "Campaign not found")
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
    key = build_media_key("tenants", tenant.slug, "campaigns", campaign.id, "banner", filename)

    storage_delete_by_url(campaign.banner_image_url)
    campaign.banner_image_url = storage_save(key, contents, file.content_type)
    campaign.banner_enabled = True
    if not campaign.banner_position:
        campaign.banner_position = "top"
    campaign.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(campaign)
    return campaign
