from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import asc, or_
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..db import get_db
from ..domain.config.operating_hours import load_operating_hours, is_open_now
from ..domain.config.payment_methods import load_payment_methods
from ..tenancy import TenantContext, get_tenant_context

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _normalize_store_token(value: str | None) -> str:
    return "".join(ch for ch in (value or "").strip().lower() if ch.isalnum())


def _resolve_catalog_store(db: Session, tenant_id: str, store: str | None) -> models.Store:
    stores = (
        db.query(models.Store)
        .filter(models.Store.tenant_id == tenant_id, models.Store.is_active.is_(True))
        .order_by(models.Store.name.asc())
        .all()
    )
    if not stores:
        raise ValueError("No active store")
    if not store:
        return stores[0]

    store_token = store.strip().lower()
    normalized_token = _normalize_store_token(store)
    for item in stores:
        if item.id == store:
            return item
        if (item.slug or "").lower() == store_token:
            return item
        if _normalize_store_token(item.name) == normalized_token:
            return item
    return stores[0]


@router.get("", response_model=schemas.CatalogOut)
def get_catalog(
    store: str | None = Query(default=None, description="Store id or slug"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    try:
        selected_store = _resolve_catalog_store(db, tenant.id, store)
    except ValueError:
        return {
            "categories": [],
            "products": [],
            "campaign_banners": [],
            "payment_methods": [],
        }

    categories = (
        db.query(models.Category)
        .filter(models.Category.tenant_id == tenant.id, models.Category.is_active.is_(True))
        .filter(or_(models.Category.store_id == selected_store.id, models.Category.store_id.is_(None)))
        .order_by(asc(models.Category.display_order), asc(models.Category.name))
        .all()
    )
    active_category_ids = [category.id for category in categories]
    products = (
        db.query(models.Product)
        .options(selectinload(models.Product.additional_links))
        .filter(models.Product.tenant_id == tenant.id)
        .filter(models.Product.is_active.is_(True))
        .filter(or_(models.Product.store_id == selected_store.id, models.Product.store_id.is_(None)))
        .filter(or_(models.Product.category_id.is_(None), models.Product.category_id.in_(active_category_ids)))
        .order_by(
            asc(models.Product.category_id),
            asc(models.Product.display_order),
            asc(models.Product.name),
        )
        .all()
    )
    additionals = (
        db.query(models.Additional)
        .filter(models.Additional.tenant_id == tenant.id, models.Additional.is_active.is_(True))
        .filter(or_(models.Additional.store_id == selected_store.id, models.Additional.store_id.is_(None)))
        .order_by(asc(models.Additional.display_order), asc(models.Additional.name))
        .all()
    )
    now = datetime.now(timezone.utc)
    campaign_banners = (
        db.query(models.Campaign)
        .filter(models.Campaign.tenant_id == tenant.id)
        .filter(models.Campaign.is_active.is_(True))
        .filter(models.Campaign.banner_enabled.is_(True))
        .filter(models.Campaign.banner_image_url.isnot(None))
        .filter(models.Campaign.banner_image_url != "")
        .filter(or_(models.Campaign.starts_at.is_(None), models.Campaign.starts_at <= now))
        .filter(or_(models.Campaign.ends_at.is_(None), models.Campaign.ends_at >= now))
        .order_by(models.Campaign.created_at.desc())
        .all()
    )
    campaign_store_rows = (
        db.query(models.CampaignStore.campaign_id, models.CampaignStore.store_id)
        .filter(models.CampaignStore.tenant_id == tenant.id)
        .all()
    )
    campaign_store_map: dict[str, set[str]] = {}
    for campaign_id, store_id in campaign_store_rows:
        campaign_store_map.setdefault(campaign_id, set()).add(store_id)
    campaign_banners = [
        campaign
        for campaign in campaign_banners
        if not campaign_store_map.get(campaign.id) or selected_store.id in campaign_store_map[campaign.id]
    ]
    config = (
        db.query(models.OperationsConfig)
        .filter(models.OperationsConfig.tenant_id == tenant.id)
        .first()
    )
    operating_hours = load_operating_hours(getattr(selected_store, "operating_hours", None))
    if not operating_hours:
        operating_hours = load_operating_hours(config.operating_hours if config else None)
    payment_methods = load_payment_methods(
        getattr(selected_store, "payment_methods", None) or (config.payment_methods if config else None)
    )
    return {
        "categories": categories,
        "products": products,
        "additionals": additionals,
        "campaign_banners": campaign_banners,
        "cover_image_url": getattr(selected_store, "cover_image_url", None) or (config.cover_image_url if config else None),
        "operating_hours": operating_hours,
        "is_open": is_open_now(operating_hours),
        "sla_minutes": int(getattr(selected_store, "sla_minutes", 0) or (config.sla_minutes if config else 0) or 0),
        "delivery_enabled": bool(getattr(selected_store, "is_delivery", True)),
        "whatsapp_contact_phone": getattr(selected_store, "whatsapp_contact_phone", None)
        or (config.whatsapp_contact_phone if config else None),
        "payment_methods": payment_methods,
        "selected_store_id": selected_store.id,
        "selected_store_slug": selected_store.slug,
        "selected_store_name": selected_store.name,
    }
