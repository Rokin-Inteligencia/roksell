from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app import models
from app.auth.dependencies import require_roles, get_current_user_optional
from app.db import get_db
from app.domain.tenancy.access import user_accessible_store_ids
from app.schemas import OrderOut, OrderListItem
from app.security import verify_order_tracking_token
from app.tenancy import TenantContext, get_tenant_context

router = APIRouter(prefix="/orders", tags=["orders"])


def _normalize_requested_store_ids(store_ids: list[str] | None) -> list[str]:
    if not store_ids:
        return []
    unique: list[str] = []
    for item in store_ids:
        value = (item or "").strip()
        if value and value not in unique:
            unique.append(value)
    return unique


def _resolve_order_scope_store_ids(
    db: Session,
    tenant_id: str,
    user: models.User,
    requested_store_ids: list[str] | None,
) -> list[str] | None:
    requested = _normalize_requested_store_ids(requested_store_ids)
    if user.role == models.UserRole.owner:
        if not requested:
            return None
        allowed_owner_ids = set(user_accessible_store_ids(db=db, tenant_id=tenant_id, user=user))
        invalid = [item for item in requested if item not in allowed_owner_ids]
        if invalid:
            raise HTTPException(status_code=403, detail="store_ids contains store without access")
        return requested

    allowed_store_ids = user_accessible_store_ids(db=db, tenant_id=tenant_id, user=user)
    if not allowed_store_ids:
        return []
    if not requested:
        return allowed_store_ids
    invalid = [item for item in requested if item not in set(allowed_store_ids)]
    if invalid:
        raise HTTPException(status_code=403, detail="store_ids contains store without access")
    return requested


@router.get("", response_model=list[OrderListItem])
def list_orders(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
    days: int | None = Query(default=30, ge=0),
    status: str | None = Query(default=None),
    customer: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    page: int = Query(default=1, ge=1),
    order_by: str | None = Query(default="created_at"),
    order_dir: str | None = Query(default="desc"),
    store_ids: list[str] | None = Query(default=None),
):
    scoped_store_ids = _resolve_order_scope_store_ids(db, tenant.id, user, store_ids)
    if scoped_store_ids is not None and not scoped_store_ids:
        return []

    query = (
        db.query(
            models.Order.id.label("id"),
            models.Order.created_at.label("created_at"),
            models.Order.delivery_date.label("delivery_date"),
            models.Order.status.label("status"),
            models.Order.total_cents.label("total_cents"),
            models.Order.store_id.label("store_id"),
            models.Order.notes.label("notes"),
            models.Customer.name.label("customer_name"),
        )
        .join(models.Customer, models.Customer.id == models.Order.customer_id)
        .filter(
            models.Order.tenant_id == tenant.id,
            models.Customer.tenant_id == tenant.id,
        )
    )
    if scoped_store_ids is not None:
        query = query.filter(models.Order.store_id.in_(scoped_store_ids))

    if days:
        start_dt = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(models.Order.created_at >= start_dt)

    if status:
        query = query.filter(models.Order.status == status)

    if customer:
        c = f"%{customer}%"
        query = query.filter(or_(models.Customer.name.ilike(c), models.Customer.phone.ilike(c)))

    order_key = (order_by or "created_at").strip().lower()
    direction = (order_dir or "desc").strip().lower()
    if direction not in {"asc", "desc"}:
        direction = "desc"
    if order_key == "delivery_date":
        if direction == "asc":
            query = query.order_by(
                models.Order.delivery_date.is_(None),
                models.Order.delivery_date.asc(),
                models.Order.created_at.desc(),
            )
        else:
            query = query.order_by(
                models.Order.delivery_date.is_(None),
                models.Order.delivery_date.desc(),
                models.Order.created_at.desc(),
            )
    else:
        query = query.order_by(
            models.Order.created_at.asc() if direction == "asc" else models.Order.created_at.desc()
        )

    offset_val = (page - 1) * limit
    query = query.offset(offset_val).limit(limit)
    rows = query.all()
    return [
        OrderListItem(
            id=str(r.id),
            customer_name=r.customer_name,
            created_at=r.created_at,
            delivery_date=getattr(r, "delivery_date", None),
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            total_cents=int(r.total_cents or 0),
            store_id=getattr(r, "store_id", None),
            notes=getattr(r, "notes", None),
        )
        for r in rows
    ]


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User | None = Depends(get_current_user_optional),
    token: str | None = Query(default=None, description="Tracking token for public access"),
):
    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id,
            models.Order.tenant_id == tenant.id,
        )
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if user is not None:
        scoped_store_ids = _resolve_order_scope_store_ids(db, tenant.id, user, None)
        order_store_id = getattr(order, "store_id", None)
        if scoped_store_ids is not None:
            if not order_store_id or order_store_id not in set(scoped_store_ids):
                raise HTTPException(status_code=404, detail="Order not found")

    pickup = bool(getattr(order, "address_id", None) is None)
    subtotal = int(getattr(order, "subtotal_cents", 0))
    shipping = 0 if pickup else int(getattr(order, "shipping_cents", 0) or 0)
    discount = int(getattr(order, "discount_cents", 0) or 0)
    total = int(getattr(order, "total_cents", subtotal + shipping - discount))

    payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.order_id == order.id,
            models.Payment.tenant_id == tenant.id,
        )
        .first()
    )
    payment_method = payment.method.value if getattr(payment, "method", None) else None
    payment_status = payment.status.value if getattr(payment, "status", None) else None

    delivery = (
        db.query(models.Delivery)
        .filter(
            models.Delivery.order_id == order.id,
            models.Delivery.tenant_id == tenant.id,
        )
        .first()
    )
    delivery_status = (
        delivery.status.value
        if delivery is not None
        else ("PICKUP" if pickup else "PENDING")
    )

    customer = (
        db.query(models.Customer)
        .filter(
            models.Customer.id == order.customer_id,
            models.Customer.tenant_id == tenant.id,
        )
        .first()
    )
    if user is None:
        if not token:
            raise HTTPException(status_code=401, detail="Missing tracking token")
        if not customer or not verify_order_tracking_token(token, order.id, customer.phone):
            raise HTTPException(status_code=403, detail="Invalid tracking token")

    delivery_postal_code = None
    delivery_street = None
    delivery_number = None
    delivery_complement = None
    delivery_district = None
    delivery_city = None
    delivery_state = None
    delivery_reference = None
    if not pickup and getattr(order, "address_id", None):
        address = (
            db.query(models.CustomerAddress)
            .filter(
                models.CustomerAddress.id == order.address_id,
                models.CustomerAddress.tenant_id == tenant.id,
            )
            .first()
        )
        if address is not None:
            delivery_postal_code = getattr(address, "postal_code", None)
            delivery_street = getattr(address, "street", None)
            delivery_number = getattr(address, "number", None)
            delivery_complement = getattr(address, "complement", None)
            delivery_district = getattr(address, "district", None)
            delivery_city = getattr(address, "city", None)
            delivery_state = getattr(address, "state", None)
            delivery_reference = getattr(address, "reference", None)

    store_payload = None
    store = None
    store_id = getattr(order, "store_id", None)
    if store_id:
        store = (
            db.query(models.Store)
            .filter(
                models.Store.id == store_id,
                models.Store.tenant_id == tenant.id,
            )
            .first()
        )
        if store is not None:
            store_payload = {
                "id": str(store.id),
                "name": getattr(store, "name", None),
                "postal_code": getattr(store, "postal_code", None),
                "street": getattr(store, "street", None),
                "number": getattr(store, "number", None),
                "complement": getattr(store, "complement", None),
                "district": getattr(store, "district", None),
                "city": getattr(store, "city", None),
                "state": getattr(store, "state", None),
                "reference": getattr(store, "reference", None),
            }

    items_rows = (
        db.query(models.OrderItem, models.Product)
        .join(models.Product, models.Product.id == models.OrderItem.product_id)
        .filter(
            models.OrderItem.order_id == order.id,
            models.OrderItem.tenant_id == tenant.id,
            models.Product.tenant_id == tenant.id,
        )
        .all()
    )
    items_out = [
        {
            "name": product.name,
            "product_id": item.product_id,
            "quantity": item.quantity,
            "unit_price_cents": item.unit_price_cents,
        }
        for (item, product) in items_rows
    ]
    cfg = (
        db.query(models.OperationsConfig)
        .filter(models.OperationsConfig.tenant_id == tenant.id)
        .first()
    )
    store_contact_phone = getattr(store, "whatsapp_contact_phone", None) if store_id and store is not None else None

    return {
        "id": str(order.id),
        "status": getattr(order, "status", "pending"),
        "pickup": bool(pickup),
        "created_at": getattr(order, "created_at", None),
        "delivery_date": getattr(order, "delivery_date", None),
        "customer_id": getattr(order, "customer_id", None),
        "customer_name": getattr(customer, "name", None),
        "whatsapp_contact_phone": store_contact_phone or getattr(cfg, "whatsapp_contact_phone", None),
        "whatsapp_order_message": getattr(cfg, "whatsapp_order_message", None),
        "pix_key": getattr(cfg, "pix_key", None),
        "notes": getattr(order, "notes", None),
        "subtotal_cents": subtotal,
        "shipping_cents": (0 if pickup else shipping),
        "discount_cents": discount,
        "total_cents": total,
        "items": items_out,
        "store_id": getattr(order, "store_id", None),
        "store": store_payload,
        "payment": {
            "method": payment_method,
            "status": payment_status,
        },
        "delivery": {
            "status": delivery_status,
            "postal_code": delivery_postal_code,
            "street": delivery_street,
            "number": delivery_number,
            "complement": delivery_complement,
            "district": delivery_district,
            "city": delivery_city,
            "state": delivery_state,
            "reference": delivery_reference,
        },
    }
