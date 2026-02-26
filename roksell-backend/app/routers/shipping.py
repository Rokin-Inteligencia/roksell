from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.domain.config.shipping_method import load_shipping_method
from app.services.shipping_distance import (
    distance_from_store,
    shipping_override_for_postal_code,
    tier_amount_for_km,
)
from app.tenancy import TenantContext, get_tenant_context

router = APIRouter(prefix="/shipping", tags=["shipping"])


class ShippingItem(BaseModel):
    product_id: str
    quantity: int


class Address(BaseModel):
    street: str | None = None
    number: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    complement: str | None = None


class Geo(BaseModel):
    lat: float | None = None
    lon: float | None = None


class ShippingRequest(BaseModel):
    postal_code: str
    pickup: bool | None = False
    items: list[ShippingItem]
    address: Address | None = None
    geo: Geo | None = None
    store_id: str | None = None


class ShippingResponse(BaseModel):
    amount_cents: int | None = None
    km: float | None = None
    method: str | None = None
    undefined: bool
    reason: str | None = None


def _get_active_store(db: Session, tenant_id: str, store_id: str | None) -> models.Store:
    query = db.query(models.Store).filter(models.Store.tenant_id == tenant_id, models.Store.is_active.is_(True))
    if store_id:
        store = query.filter(models.Store.id == store_id).first()
        if not store:
            raise HTTPException(status_code=404, detail="Loja nA£o encontrada")
        return store
    store = query.order_by(models.Store.name.asc()).first()
    if not store:
        raise HTTPException(status_code=400, detail="Nenhuma loja ativa configurada")
    return store


def _format_address(addr: Address | None) -> str | None:
    if not addr:
        return None
    parts: list[str] = []
    if (street := (addr.street or "").strip()):
        if (number := (addr.number or "").strip()):
            parts.append(f"{street}, {number}")
        else:
            parts.append(street)
    if (district := (addr.district or "").strip()):
        parts.append(district)
    if (city := (addr.city or "").strip()):
        state = (addr.state or "").strip()
        parts.append(f"{city} - {state}" if state else city)
    if (postal := (addr.postal_code or "").strip()):
        parts.append(postal)
    parts.append("Brasil")
    out = ", ".join(p for p in parts if p)
    return out or None


@router.post("/quote", response_model=ShippingResponse)
async def quote_shipping(
    req: ShippingRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    store = _get_active_store(db, tenant.id, req.store_id)
    if not req.pickup and not store.is_delivery:
        raise HTTPException(status_code=400, detail="Loja selecionada nA£o aceita entregas")

    if req.pickup:
        return {"amount_cents": 0, "method": "pickup", "undefined": False}
    method = load_shipping_method(getattr(store, "shipping_method", None))
    if method != "distance":
        return {"undefined": True, "reason": "method_not_supported", "method": method}

    override = shipping_override_for_postal_code(db, tenant.id, req.postal_code)
    if override is not None:
        return {"amount_cents": int(override), "method": "override", "undefined": False}

    destination_lat = req.geo.lat if req.geo else None
    destination_lon = req.geo.lon if req.geo else None
    destination_address = _format_address(req.address)

    km = await distance_from_store(
        db,
        tenant_id=tenant.id,
        store_id=store.id,
        dest_lat=destination_lat,
        dest_lon=destination_lon,
        dest_address=destination_address,
    )
    if km is None:
        return {"undefined": True, "reason": "distance_fail"}

    amount = tier_amount_for_km(db, tenant.id, km, store_id=store.id)
    if amount is None:
        return {"undefined": True, "reason": "out_of_area", "km": round(km, 2)}
    amount = int(amount) + int(getattr(store, "shipping_fixed_fee_cents", 0) or 0)

    return {
        "amount_cents": int(amount),
        "km": round(km, 2),
        "method": "distance",
        "undefined": False,
    }
