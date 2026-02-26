from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import require_module, require_roles
from app.db import get_db
from app.domain.tenancy.access import user_accessible_store_ids
from app.tenancy import TenantContext

router = APIRouter(prefix="/admin/shipping", tags=["admin-shipping"])

MAX_DISTANCE_TIERS = 20


def _normalize_distance_tiers(
    tiers: list[schemas.ShippingDistanceTierIn],
) -> list[dict]:
    if len(tiers) > MAX_DISTANCE_TIERS:
        raise HTTPException(status_code=400, detail="Maximo de 20 faixas de distancia")
    normalized: list[dict] = []
    for idx, tier in enumerate(tiers, start=1):
        km_min = float(tier.km_min)
        km_max = float(tier.km_max)
        amount_cents = int(tier.amount_cents)
        if km_min < 0 or km_max <= km_min:
            raise HTTPException(status_code=400, detail=f"Intervalo invalido na faixa {idx}")
        if amount_cents < 0:
            raise HTTPException(status_code=400, detail=f"Valor invalido na faixa {idx}")
        normalized.append(
            {
                "km_min": km_min,
                "km_max": km_max,
                "amount_cents": amount_cents,
            }
        )
    normalized.sort(key=lambda item: item["km_min"])
    for idx in range(1, len(normalized)):
        if normalized[idx]["km_min"] < normalized[idx - 1]["km_max"]:
            raise HTTPException(status_code=400, detail="Faixas de distancia sobrepostas")
    return normalized


def _tier_out(row: models.ShippingDistanceTier) -> schemas.ShippingDistanceTierOut:
    return schemas.ShippingDistanceTierOut(
        km_min=float(row.km_min),
        km_max=float(row.km_max),
        amount_cents=int(row.amount_cents),
    )


def _resolve_store_id_or_400(
    db: Session,
    tenant_id: str,
    user: models.User,
    store_id: str | None,
) -> str:
    value = (store_id or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="store_id is required")
    allowed_store_ids = user_accessible_store_ids(db=db, tenant_id=tenant_id, user=user)
    if value not in allowed_store_ids:
        raise HTTPException(status_code=403, detail="Store access denied")
    store = (
        db.query(models.Store.id)
        .filter(models.Store.id == value, models.Store.tenant_id == tenant_id)
        .first()
    )
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return value


@router.get("/tiers", response_model=list[schemas.ShippingDistanceTierOut])
def list_distance_tiers(
    store_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("stores")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    resolved_store_id = _resolve_store_id_or_400(db, tenant.id, user, store_id)
    tiers = (
        db.query(models.ShippingDistanceTier)
        .filter(
            models.ShippingDistanceTier.tenant_id == tenant.id,
            models.ShippingDistanceTier.store_id == resolved_store_id,
        )
        .order_by(models.ShippingDistanceTier.km_min.asc())
        .all()
    )
    return [_tier_out(tier) for tier in tiers]


@router.put("/tiers", response_model=list[schemas.ShippingDistanceTierOut])
def replace_distance_tiers(
    payload: list[schemas.ShippingDistanceTierIn],
    store_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("stores")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    resolved_store_id = _resolve_store_id_or_400(db, tenant.id, user, store_id)
    normalized = _normalize_distance_tiers(payload)
    (
        db.query(models.ShippingDistanceTier)
        .filter(
            models.ShippingDistanceTier.tenant_id == tenant.id,
            models.ShippingDistanceTier.store_id == resolved_store_id,
        )
        .delete(synchronize_session=False)
    )
    for tier in normalized:
        db.add(
            models.ShippingDistanceTier(
                tenant_id=tenant.id,
                store_id=resolved_store_id,
                km_min=tier["km_min"],
                km_max=tier["km_max"],
                amount_cents=tier["amount_cents"],
            )
        )
    db.commit()
    return [
        schemas.ShippingDistanceTierOut(
            km_min=tier["km_min"],
            km_max=tier["km_max"],
            amount_cents=tier["amount_cents"],
        )
        for tier in normalized
    ]
