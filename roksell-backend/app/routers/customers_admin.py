from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.phone import normalize_phone
from app.auth.dependencies import require_module_action, require_roles
from app.db import get_db
from app.tenancy import TenantContext

router = APIRouter(prefix="/admin/customers", tags=["admin-customers"])


def _customer_out_payload(customer: models.Customer, origin_store_name: str | None = None) -> dict:
    return {
        "id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "is_active": customer.is_active,
        "birthday": customer.birthday,
        "created_at": customer.created_at,
        "origin_store_id": customer.origin_store_id,
        "origin_store_name": origin_store_name,
    }


@router.get("", response_model=list[schemas.CustomerOut])
def list_customers(
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    active: str | None = Query("true"),
    search: str | None = Query(None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("customers", "view")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    normalized_active = (active or "").strip().lower()
    if normalized_active in ("", "all"):
        active_filter = None
    elif normalized_active in ("true", "1", "t", "yes", "y", "sim"):
        active_filter = True
    elif normalized_active in ("false", "0", "f", "no", "n", "nao"):
        active_filter = False
    else:
        raise HTTPException(status_code=422, detail="active must be true, false, or all")

    offset = (page - 1) * limit
    query = db.query(models.Customer).filter(models.Customer.tenant_id == tenant.id)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                models.Customer.name.ilike(term),
                models.Customer.phone.ilike(term),
            ),
        )
    if active_filter is True:
        query = query.filter(models.Customer.is_active.is_(True))
    elif active_filter is False:
        query = query.filter(models.Customer.is_active.is_(False))

    customers = query.order_by(models.Customer.created_at.desc()).offset(offset).limit(limit).all()
    store_ids = [customer.origin_store_id for customer in customers if customer.origin_store_id]
    store_name_rows = (
        db.query(models.Store.id, models.Store.name)
        .filter(models.Store.tenant_id == tenant.id, models.Store.id.in_(store_ids))
        .all()
    )
    store_name_map = {row[0]: row[1] for row in store_name_rows}
    return [
        _customer_out_payload(
            customer,
            origin_store_name=store_name_map.get(customer.origin_store_id) if customer.origin_store_id else None,
        )
        for customer in customers
    ]


@router.patch("/{customer_id}", response_model=schemas.CustomerOut)
def update_customer(
    customer_id: str,
    payload: schemas.CustomerUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("customers", "edit")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.id == customer_id, models.Customer.tenant_id == tenant.id)
        .first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if payload.name is not None:
        customer.name = payload.name
    if payload.phone is not None:
        normalized = normalize_phone(payload.phone)
        if not normalized:
            raise HTTPException(status_code=422, detail="Invalid phone")
        customer.phone = normalized
    if payload.birthday is not None:
        customer.birthday = payload.birthday
    if payload.is_active is not None:
        customer.is_active = payload.is_active

    db.commit()
    db.refresh(customer)
    origin_store_name = None
    if customer.origin_store_id:
        store = (
            db.query(models.Store)
            .filter(models.Store.id == customer.origin_store_id, models.Store.tenant_id == tenant.id)
            .first()
        )
        origin_store_name = store.name if store else None
    return _customer_out_payload(customer, origin_store_name=origin_store_name)
