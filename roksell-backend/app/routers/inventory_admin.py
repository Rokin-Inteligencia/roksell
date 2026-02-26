import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import require_module_action, require_roles
from app.db import get_db
from app.domain.shipping.store_timezone import DEFAULT_STORE_TIMEZONE
from app.domain.tenancy.access import user_accessible_store_ids
from app.tenancy import TenantContext

router = APIRouter(prefix="/admin/inventory", tags=["admin-inventory"])


def _get_store(db: Session, tenant_id: str, store_id: str) -> models.Store | None:
    return (
        db.query(models.Store)
        .filter(models.Store.id == store_id, models.Store.tenant_id == tenant_id)
        .first()
    )


def _get_product(db: Session, tenant_id: str, product_id: str) -> models.Product | None:
    return (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.tenant_id == tenant_id)
        .first()
    )


@router.get("/stores", response_model=list[schemas.StoreOut])
def list_inventory_stores(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("inventory", "view")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    allowed_store_ids = user_accessible_store_ids(db=db, tenant_id=tenant.id, user=user)
    stores = (
        db.query(models.Store)
        .filter(models.Store.tenant_id == tenant.id, models.Store.id.in_(allowed_store_ids))
        .order_by(models.Store.name.asc())
        .all()
    )
    return [
        schemas.StoreOut(
            id=store.id,
            name=store.name,
            slug=store.slug,
            timezone=(store.timezone or DEFAULT_STORE_TIMEZONE),
            is_active=store.is_active,
            is_delivery=store.is_delivery,
            allow_preorder_when_closed=bool(getattr(store, "allow_preorder_when_closed", True)),
            lat=float(store.lat),
            lon=float(store.lon),
            closed_dates=[],
            operating_hours=[],
            postal_code=store.postal_code,
            street=store.street,
            number=store.number,
            district=store.district,
            city=store.city,
            state=store.state,
            complement=store.complement,
            reference=store.reference,
            phone=store.phone,
        )
        for store in stores
    ]


@router.get("", response_model=list[schemas.StoreInventoryOut])
def list_inventory(
    store_id: str = Query(..., description="ID da loja"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("inventory", "view")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    store = _get_store(db, tenant.id, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Loja nao encontrada")

    allowed_store_ids = user_accessible_store_ids(db=db, tenant_id=tenant.id, user=user)
    if store_id not in allowed_store_ids:
        raise HTTPException(status_code=403, detail="Store access denied")

    products = (
        db.query(models.Product)
        .filter(
            models.Product.tenant_id == tenant.id,
            models.Product.is_active.is_(True),
            (models.Product.store_id == store_id) | (models.Product.store_id.is_(None)),
        )
        .order_by(models.Product.display_order.asc(), models.Product.name.asc())
        .all()
    )
    inventory_rows = (
        db.query(models.StoreInventory)
        .filter(
            models.StoreInventory.tenant_id == tenant.id,
            models.StoreInventory.store_id == store_id,
        )
        .all()
    )
    qty_by_product = {row.product_id: int(row.quantity or 0) for row in inventory_rows}

    return [
        schemas.StoreInventoryOut(
            product_id=product.id,
            product_name=product.name,
            store_id=store_id,
            quantity=qty_by_product.get(product.id, 0),
        )
        for product in products
    ]


@router.post("", response_model=schemas.StoreInventoryOut)
def upsert_inventory(
    payload: schemas.StoreInventoryUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("inventory", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    store = _get_store(db, tenant.id, payload.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Loja nao encontrada")

    allowed_store_ids = user_accessible_store_ids(db=db, tenant_id=tenant.id, user=user)
    if payload.store_id not in allowed_store_ids:
        raise HTTPException(status_code=403, detail="Store access denied")

    product = _get_product(db, tenant.id, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    if product.store_id and product.store_id != payload.store_id:
        raise HTTPException(status_code=400, detail="Produto nao pertence a loja informada")

    if payload.quantity < 0:
        raise HTTPException(status_code=400, detail="Quantidade deve ser maior ou igual a zero")

    inventory = (
        db.query(models.StoreInventory)
        .filter(
            models.StoreInventory.tenant_id == tenant.id,
            models.StoreInventory.store_id == payload.store_id,
            models.StoreInventory.product_id == payload.product_id,
        )
        .with_for_update()
        .first()
    )
    if not inventory:
        inventory = models.StoreInventory(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            store_id=payload.store_id,
            product_id=payload.product_id,
            quantity=payload.quantity,
        )
        db.add(inventory)
    else:
        inventory.quantity = payload.quantity

    db.commit()
    db.refresh(inventory)
    return schemas.StoreInventoryOut(
        product_id=inventory.product_id,
        product_name=product.name,
        store_id=inventory.store_id,
        quantity=int(inventory.quantity or 0),
    )
