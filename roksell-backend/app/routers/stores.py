from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.domain.config.order_statuses import (
    load_order_final_statuses,
    load_order_status_colors,
    load_order_statuses,
)
from app.domain.config.payment_methods import load_payment_methods
from app.domain.config.shipping_method import load_shipping_method
from app.domain.shipping.store_calendar import load_store_closed_dates
from app.domain.shipping.store_hours import load_store_operating_hours
from app.domain.shipping.store_timezone import DEFAULT_STORE_TIMEZONE
from app.db import get_db
from app.tenancy import TenantContext, get_tenant_context

router = APIRouter(prefix="/stores", tags=["stores"])


def _store_payload(store: models.Store) -> dict:
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


@router.get("", response_model=list[schemas.StoreOut])
def list_public_stores(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    stores = (
        db.query(models.Store)
        .filter(models.Store.tenant_id == tenant.id, models.Store.is_active.is_(True))
        .order_by(models.Store.name.asc())
        .all()
    )
    return [_store_payload(store) for store in stores]
