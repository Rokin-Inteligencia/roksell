import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from .. import schemas
from ..auth.dependencies import require_roles
from ..db import get_db
from app.domain.config.order_statuses import load_order_final_statuses, load_order_statuses
from app.domain.tenancy.access import (
    user_accessible_store_ids,
    user_group_permissions,
    permission_allows_action,
    user_allowed_modules,
    normalize_tenant_modules,
)
from app.services.admin_onboarding import (
    get_onboarding_state as svc_get_onboarding_state,
    complete_onboarding as svc_complete_onboarding,
    enable_onboarding_test_mode as svc_enable_onboarding_test_mode,
)
from app.services.whatsapp import send_order_status_whatsapp
from ..tenancy import TenantContext, get_tenant_context

router = APIRouter(prefix="/admin", tags=["admin"])


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., description="Novo status do pedido")


def _replace_datetime_date(source: datetime | None, target_date) -> datetime:
    if isinstance(source, datetime):
        return datetime.combine(target_date, source.timetz())
    return datetime.combine(target_date, datetime.now(timezone.utc).timetz())


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
    requested_store_ids: list[str] | None = None,
) -> list[str] | None:
    requested = _normalize_requested_store_ids(requested_store_ids)
    if user.role == models.UserRole.owner:
        if not requested:
            return None
        owner_allowed_ids = set(user_accessible_store_ids(db=db, tenant_id=tenant_id, user=user))
        invalid = [item for item in requested if item not in owner_allowed_ids]
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


def _tenant_config(db: Session, tenant_id: str) -> models.OperationsConfig | None:
    return (
        db.query(models.OperationsConfig)
        .filter(models.OperationsConfig.tenant_id == tenant_id)
        .first()
    )


def _store_or_none(db: Session, tenant_id: str, store_id: str | None) -> models.Store | None:
    if not store_id:
        return None
    return (
        db.query(models.Store)
        .filter(models.Store.id == store_id, models.Store.tenant_id == tenant_id)
        .first()
    )


def _status_config_for_scope(
    db: Session,
    tenant_id: str,
    store_ids: list[str] | None,
) -> tuple[list[str], list[str], dict[str, str] | None, str | None]:
    cfg = _tenant_config(db, tenant_id)
    fallback_statuses = load_order_statuses(cfg.order_statuses if cfg else None)
    fallback_final = load_order_final_statuses(cfg.order_final_statuses if cfg else None, fallback_statuses)

    target_store_ids: list[str]
    if store_ids is None:
        rows = db.query(models.Store.id).filter(models.Store.tenant_id == tenant_id).all()
        target_store_ids = [row[0] for row in rows]
    else:
        target_store_ids = list(store_ids)

    statuses_merged: list[str] = []
    final_merged: list[str] = []
    colors_merged: dict[str, str] = {}
    canceled_color = getattr(cfg, "order_status_canceled_color", None)

    if not target_store_ids:
        return fallback_statuses, fallback_final, getattr(cfg, "order_status_colors", None), canceled_color

    stores = (
        db.query(models.Store)
        .filter(models.Store.tenant_id == tenant_id, models.Store.id.in_(target_store_ids))
        .all()
    )
    if not stores:
        return fallback_statuses, fallback_final, getattr(cfg, "order_status_colors", None), canceled_color

    for store in stores:
        current_statuses = load_order_statuses(getattr(store, "order_statuses", None) or (cfg.order_statuses if cfg else None))
        for status in current_statuses:
            if status not in statuses_merged:
                statuses_merged.append(status)
        current_final = load_order_final_statuses(
            getattr(store, "order_final_statuses", None) or (cfg.order_final_statuses if cfg else None),
            current_statuses,
        )
        for status in current_final:
            if status not in final_merged:
                final_merged.append(status)
        raw_colors = getattr(store, "order_status_colors", None) or getattr(cfg, "order_status_colors", None)
        if raw_colors:
            try:
                parsed = json.loads(raw_colors)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    if key not in colors_merged and isinstance(value, str):
                        colors_merged[key] = value
        if not canceled_color:
            canceled_color = getattr(store, "order_status_canceled_color", None) or canceled_color

    if not statuses_merged:
        statuses_merged = fallback_statuses
    if not final_merged:
        final_merged = fallback_final
    return statuses_merged, final_merged, (colors_merged or None), canceled_color


@router.patch("/orders/{order_id}/status")
def set_status(
    order_id: str,
    payload: OrderStatusUpdate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
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
        raise HTTPException(404, "Order not found")
    scoped_store_ids = _resolve_order_scope_store_ids(db, tenant.id, user)
    if scoped_store_ids is not None:
        order_store_id = getattr(order, "store_id", None)
        if not order_store_id or order_store_id not in set(scoped_store_ids):
            raise HTTPException(404, "Order not found")
    cfg = _tenant_config(db, tenant.id)
    store = _store_or_none(db, tenant.id, getattr(order, "store_id", None))
    allowed = set(load_order_statuses(getattr(store, "order_statuses", None) or (cfg.order_statuses if cfg else None)))
    new_status = payload.status
    if new_status not in allowed:
        raise HTTPException(400, "Invalid status")
    previous = getattr(order, "status", None)
    order.status = new_status
    db.commit()
    if new_status != previous:
        background.add_task(send_order_status_whatsapp, tenant_id=tenant.id, order_id=order.id, status=new_status)
    return {"ok": True, "status": order.status}


@router.patch("/payments/{order_id}/confirm")
def confirm_payment(
    order_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.order_id == order_id,
            models.Payment.tenant_id == tenant.id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(404, "Payment not found")
    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == payment.order_id,
            models.Order.tenant_id == tenant.id,
        )
        .first()
    )
    if not order:
        raise HTTPException(404, "Order not found")
    scoped_store_ids = _resolve_order_scope_store_ids(db, tenant.id, user)
    if scoped_store_ids is not None:
        order_store_id = getattr(order, "store_id", None)
        if not order_store_id or order_store_id not in set(scoped_store_ids):
            raise HTTPException(404, "Order not found")
    payment.status = models.PaymentStatus.confirmed
    db.commit()
    return {"ok": True}


@router.patch("/orders/{order_id}")
def update_order(
    order_id: str,
    payload: schemas.OrderAdminUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
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
        raise HTTPException(404, "Order not found")
    scoped_store_ids = _resolve_order_scope_store_ids(db, tenant.id, user)
    if scoped_store_ids is not None:
        order_store_id = getattr(order, "store_id", None)
        if not order_store_id or order_store_id not in set(scoped_store_ids):
            raise HTTPException(404, "Order not found")

    if payload.customer_id:
        customer = (
            db.query(models.Customer)
            .filter(
                models.Customer.id == payload.customer_id,
                models.Customer.tenant_id == tenant.id,
            )
            .first()
        )
        if not customer:
            raise HTTPException(404, "Customer not found")
        order.customer_id = customer.id

    payment = None

    if payload.delivery_date is not None:
        order.delivery_date = payload.delivery_date
    if payload.received_date is not None:
        order.created_at = _replace_datetime_date(getattr(order, "created_at", None), payload.received_date)
        payment = (
            db.query(models.Payment)
            .filter(
                models.Payment.order_id == order.id,
                models.Payment.tenant_id == tenant.id,
            )
            .first()
        )
        if payment:
            payment.created_at = _replace_datetime_date(
                getattr(payment, "created_at", None),
                payload.received_date,
            )

    if payload.items is not None:
        if len(payload.items) == 0:
            raise HTTPException(400, "Itens vazios")
        product_ids = [item.product_id for item in payload.items]
        products = (
            db.query(models.Product)
            .filter(
                models.Product.tenant_id == tenant.id,
                models.Product.id.in_(product_ids),
            )
            .all()
        )
        products_map = {p.id: p for p in products}
        missing = [pid for pid in product_ids if pid not in products_map]
        if missing:
            raise HTTPException(400, f"Invalid product: {missing[0]}")

        db.query(models.OrderItem).filter(
            models.OrderItem.order_id == order.id,
            models.OrderItem.tenant_id == tenant.id,
        ).delete(synchronize_session=False)

        subtotal = 0
        for item in payload.items:
            product = products_map[item.product_id]
            subtotal += product.price_cents * item.quantity
            db.add(
                models.OrderItem(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant.id,
                    order_id=order.id,
                    product_id=product.id,
                    quantity=item.quantity,
                    unit_price_cents=product.price_cents,
                )
            )

        order.subtotal_cents = subtotal
        shipping = int(getattr(order, "shipping_cents", 0) or 0)
        discount = int(getattr(order, "discount_cents", 0) or 0)
        order.total_cents = max(subtotal + shipping - discount, 0)

        if payment is None:
            payment = (
                db.query(models.Payment)
                .filter(
                    models.Payment.order_id == order.id,
                    models.Payment.tenant_id == tenant.id,
                )
                .first()
            )
        if payment:
            payment.amount_cents = order.total_cents

    db.commit()
    return {"ok": True, "total_cents": order.total_cents}


@router.get("/orders/open", response_model=list[schemas.OrderListItem])
def list_open_orders(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
    limit: int = Query(default=50, ge=1, le=200),
    store_ids: list[str] | None = Query(default=None),
):
    scoped_store_ids = _resolve_order_scope_store_ids(db, tenant.id, user, store_ids)
    if scoped_store_ids is not None and not scoped_store_ids:
        return []

    _, final_statuses, _, _ = _status_config_for_scope(db, tenant.id, scoped_store_ids)

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
        .order_by(models.Order.created_at.asc())
    )
    if scoped_store_ids is not None:
        query = query.filter(models.Order.store_id.in_(scoped_store_ids))
    if final_statuses:
        query = query.filter(models.Order.status.notin_(final_statuses))
    query = query.limit(limit)
    rows = query.all()
    return [
        schemas.OrderListItem(
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


@router.get("/orders/summary", response_model=schemas.OrdersSummaryOut)
def get_orders_summary(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
    store_ids: list[str] | None = Query(default=None),
):
    scoped_store_ids = _resolve_order_scope_store_ids(db, tenant.id, user, store_ids)
    if scoped_store_ids is not None and not scoped_store_ids:
        return schemas.OrdersSummaryOut(
            open_count=0,
            revenue_today_cents=0,
            orders_today=0,
        )

    _, final_statuses, _, _ = _status_config_for_scope(db, tenant.id, scoped_store_ids)

    try:
        tz_sp = ZoneInfo("America/Sao_Paulo")
    except ZoneInfoNotFoundError:
        tz_sp = timezone(timedelta(hours=-3))

    now = datetime.now(tz_sp).astimezone(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    open_query = db.query(func.count(models.Order.id)).filter(models.Order.tenant_id == tenant.id)
    if scoped_store_ids is not None:
        open_query = open_query.filter(models.Order.store_id.in_(scoped_store_ids))
    if final_statuses:
        open_query = open_query.filter(models.Order.status.notin_(final_statuses))
    open_count = open_query.scalar() or 0

    revenue_today = (
        db.query(func.coalesce(func.sum(models.Payment.amount_cents), 0))
        .join(models.Order, models.Order.id == models.Payment.order_id)
        .filter(
            models.Payment.tenant_id == tenant.id,
            models.Payment.status.in_([models.PaymentStatus.confirmed, models.PaymentStatus.pending]),
            models.Payment.created_at >= day_start,
            models.Order.status != "canceled",
        )
    )
    if scoped_store_ids is not None:
        revenue_today = revenue_today.filter(models.Order.store_id.in_(scoped_store_ids))
    revenue_today = revenue_today.scalar() or 0

    orders_today = (
        db.query(func.count(models.Order.id))
        .filter(
            models.Order.tenant_id == tenant.id,
            models.Order.status != "canceled",
            models.Order.created_at >= day_start,
        )
    )
    if scoped_store_ids is not None:
        orders_today = orders_today.filter(models.Order.store_id.in_(scoped_store_ids))
    orders_today = orders_today.scalar() or 0

    return schemas.OrdersSummaryOut(
        open_count=int(open_count),
        revenue_today_cents=int(revenue_today),
        orders_today=int(orders_today),
    )


@router.get("/orders/status-summary", response_model=schemas.OrdersStatusSummaryOut)
def get_orders_status_summary(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
    store_ids: list[str] | None = Query(default=None),
):
    scoped_store_ids = _resolve_order_scope_store_ids(db, tenant.id, user, store_ids)
    if scoped_store_ids is not None and not scoped_store_ids:
        return schemas.OrdersStatusSummaryOut(items=[])

    order_statuses, _, _, _ = _status_config_for_scope(db, tenant.id, scoped_store_ids)
    try:
        tz_sp = ZoneInfo("America/Sao_Paulo")
    except ZoneInfoNotFoundError:
        tz_sp = timezone(timedelta(hours=-3))
    now = datetime.now(tz_sp).astimezone(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    rows = (
        db.query(models.Order.status.label("status"), func.count(models.Order.id).label("qty"))
        .filter(
            models.Order.tenant_id == tenant.id,
            models.Order.created_at >= day_start,
        )
    )
    if scoped_store_ids is not None:
        rows = rows.filter(models.Order.store_id.in_(scoped_store_ids))
    rows = rows.group_by(models.Order.status).all()
    counts = {
        (r.status.value if hasattr(r.status, "value") else str(r.status)): int(r.qty or 0)
        for r in rows
    }
    items: list[schemas.OrdersStatusCountOut] = []
    used = set()
    for status in order_statuses:
        items.append(schemas.OrdersStatusCountOut(status=status, count=int(counts.get(status, 0))))
        used.add(status)
    for status, count in counts.items():
        if status in used:
            continue
        items.append(schemas.OrdersStatusCountOut(status=status, count=int(count)))
    return schemas.OrdersStatusSummaryOut(items=items)


@router.get("/orders/status-options")
def get_orders_status_options(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
    store_ids: list[str] | None = Query(default=None),
):
    statuses, _, colors, canceled_color = _status_config_for_scope(
        db,
        tenant.id,
        _normalize_requested_store_ids(store_ids) or None,
    )
    return {
        "order_statuses": statuses,
        "order_status_colors": colors,
        "order_status_canceled_color": canceled_color,
    }


@router.get("/tenant", response_model=schemas.TenantInfoOut)
def get_tenant_info(
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    return schemas.TenantInfoOut(
        id=tenant.id,
        slug=tenant.slug,
        name=getattr(tenant, "name", tenant.slug),
        users_limit=getattr(tenant, "users_limit", 5),
    )


@router.get("/onboarding/state", response_model=schemas.OnboardingStateOut)
def get_onboarding_state(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    return svc_get_onboarding_state(db=db, tenant_id=tenant.id, user=user)


@router.post("/onboarding/complete", response_model=schemas.OnboardingCompleteOut)
async def complete_onboarding(
    payload: schemas.OnboardingCompletePayload,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    return await svc_complete_onboarding(
        db=db,
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        stores_limit=getattr(tenant, "stores_limit", None),
        user=user,
        payload=payload,
    )


@router.post("/onboarding/test-enable", response_model=schemas.OnboardingTestModeOut)
def enable_onboarding_test_mode(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    return svc_enable_onboarding_test_mode(db=db, tenant_id=tenant.id)


@router.get("/modules")
def get_tenant_modules(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    modules = user_allowed_modules(db=db, user=user, tenant_modules=tenant.modules)
    tenant_modules = normalize_tenant_modules(tenant.modules)
    permissions = user_group_permissions(db, user)
    module_access: dict[str, dict[str, bool]] = {}
    for module_key in sorted(modules):
        view_allowed = module_key in modules
        if user.role == models.UserRole.owner:
            edit_allowed = module_key in tenant_modules
        elif user.group_id:
            edit_allowed = permission_allows_action(permissions, module_key, "edit")
        else:
            edit_allowed = module_key in tenant_modules
        module_access[module_key] = {
            "view": bool(view_allowed),
            "edit": bool(edit_allowed),
        }
    return {"modules": sorted(modules), "module_access": module_access}
