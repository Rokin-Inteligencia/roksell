"""
Serviço de insights: agregações e métricas de pedidos/pagamentos por tenant.
O router admin/insights apenas orquestra (query params, auth, chamada ao serviço).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, date, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app import models, schemas


def _start_of_day(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_week(now: datetime) -> datetime:
    sod = _start_of_day(now)
    return sod - timedelta(days=sod.weekday())


def _start_of_month(now: datetime) -> datetime:
    sod = _start_of_day(now)
    return sod.replace(day=1)


def _get_tz_sp():
    try:
        return ZoneInfo("America/Sao_Paulo")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=-3))


def parse_date_range(
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime | None, datetime | None]:
    """Converte start_date/end_date (ISO) em datetime UTC para filtros."""
    tz_sp = _get_tz_sp()

    def parse_date(value: str | None, end_of_day: bool = False) -> datetime | None:
        if not value:
            return None
        try:
            if len(value) == 10:
                d = date.fromisoformat(value)
                if end_of_day:
                    return datetime.combine(d, time(23, 59, 59, 999000), tzinfo=tz_sp).astimezone(timezone.utc)
                return datetime.combine(d, time(0, 0, 0, 0), tzinfo=tz_sp).astimezone(timezone.utc)
            return datetime.fromisoformat(value).astimezone(tz_sp).astimezone(timezone.utc)
        except Exception:
            return None

    range_start = parse_date(start_date)
    range_end = parse_date(end_date, end_of_day=True)
    if range_start and not range_end:
        range_end = datetime.now(tz_sp).astimezone(timezone.utc)
    if range_end and not range_start:
        range_start = _start_of_day(range_end)
    return range_start, range_end


def get_insights(
    db: Session,
    tenant_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> schemas.InsightsOut:
    """Calcula métricas de receita, pedidos e breakdowns por categoria/loja/produto no período."""
    tz_sp = _get_tz_sp()
    range_start, range_end = parse_date_range(start_date, end_date)

    now = datetime.now(tz_sp).astimezone(timezone.utc)
    day = _start_of_day(now)
    week = _start_of_week(now)
    month = _start_of_month(now)

    payment_ok = models.Payment.status.in_(
        [models.PaymentStatus.confirmed, models.PaymentStatus.pending]
    )
    order_ok = models.Order.status != "canceled"

    def revenue_since(start_dt: datetime) -> int:
        q = (
            db.query(func.coalesce(func.sum(models.Payment.amount_cents), 0))
            .filter(
                models.Payment.tenant_id == tenant_id,
                payment_ok,
                models.Payment.created_at >= start_dt,
                order_ok,
            )
            .join(models.Order, models.Order.id == models.Payment.order_id)
        )
        return int(q.scalar() or 0)

    def orders_since(start_dt: datetime) -> int:
        q = (
            db.query(func.count(func.distinct(models.Order.id)))
            .join(models.Payment, models.Payment.order_id == models.Order.id)
            .filter(
                models.Order.tenant_id == tenant_id,
                models.Payment.tenant_id == tenant_id,
                payment_ok,
                order_ok,
                models.Payment.created_at >= start_dt,
            )
        )
        return int(q.scalar() or 0)

    revenue_today = revenue_since(day)
    revenue_week = revenue_since(week)
    revenue_month = revenue_since(month)
    orders_today = orders_since(day)
    orders_month = orders_since(month)

    range_filters = []
    if range_start:
        range_filters.append(models.Payment.created_at >= range_start)
    if range_end:
        range_filters.append(models.Payment.created_at <= range_end)

    cat_name = func.coalesce(models.Category.name, "Sem categoria").label("category_name")
    by_category = (
        db.query(
            cat_name,
            func.coalesce(
                func.sum(models.OrderItem.quantity * models.OrderItem.unit_price_cents), 0
            ).label("revenue_cents"),
        )
        .join(models.Product, models.Product.id == models.OrderItem.product_id)
        .outerjoin(models.Category, models.Category.id == models.Product.category_id)
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .join(models.Payment, models.Payment.order_id == models.Order.id)
        .filter(
            models.OrderItem.tenant_id == tenant_id,
            models.Payment.tenant_id == tenant_id,
            payment_ok,
            order_ok,
            *range_filters,
        )
        .group_by(cat_name)
        .order_by(func.sum(models.OrderItem.quantity * models.OrderItem.unit_price_cents).desc())
        .limit(10)
        .all()
    )

    store_name = func.coalesce(models.Store.name, "Sem loja").label("store_name")
    by_store = (
        db.query(
            store_name,
            func.coalesce(func.sum(models.Payment.amount_cents), 0).label("revenue_cents"),
        )
        .join(models.Order, models.Order.id == models.Payment.order_id)
        .outerjoin(
            models.Store,
            and_(
                models.Store.id == models.Order.store_id,
                models.Store.tenant_id == tenant_id,
            ),
        )
        .filter(
            models.Payment.tenant_id == tenant_id,
            models.Order.tenant_id == tenant_id,
            payment_ok,
            order_ok,
            *range_filters,
        )
        .group_by(store_name)
        .order_by(func.sum(models.Payment.amount_cents).desc())
        .all()
    )

    product_group_id = func.coalesce(models.Product.product_master_id, models.Product.id).label("product_group_id")
    prod_name = func.coalesce(
        func.max(models.ProductMaster.name_canonical),
        func.max(models.Product.name),
    ).label("product_name")
    by_product = (
        db.query(
            prod_name,
            func.coalesce(
                func.sum(models.OrderItem.quantity * models.OrderItem.unit_price_cents), 0
            ).label("revenue_cents"),
        )
        .select_from(models.Product)
        .join(models.OrderItem, models.OrderItem.product_id == models.Product.id)
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .join(models.Payment, models.Payment.order_id == models.Order.id)
        .outerjoin(
            models.ProductMaster,
            and_(
                models.ProductMaster.id == models.Product.product_master_id,
                models.ProductMaster.tenant_id == tenant_id,
            ),
        )
        .filter(
            models.Product.tenant_id == tenant_id,
            models.OrderItem.tenant_id == tenant_id,
            models.Payment.tenant_id == tenant_id,
            payment_ok,
            order_ok,
            *range_filters,
        )
        .group_by(product_group_id)
        .order_by(func.sum(models.OrderItem.quantity * models.OrderItem.unit_price_cents).desc())
        .limit(10)
        .all()
    )

    qty_by_product = (
        db.query(
            prod_name,
            func.coalesce(func.sum(models.OrderItem.quantity), 0).label("qty"),
        )
        .select_from(models.Product)
        .join(models.OrderItem, models.OrderItem.product_id == models.Product.id)
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .join(models.Payment, models.Payment.order_id == models.Order.id)
        .outerjoin(
            models.ProductMaster,
            and_(
                models.ProductMaster.id == models.Product.product_master_id,
                models.ProductMaster.tenant_id == tenant_id,
            ),
        )
        .filter(
            models.Product.tenant_id == tenant_id,
            models.OrderItem.tenant_id == tenant_id,
            models.Payment.tenant_id == tenant_id,
            payment_ok,
            order_ok,
            *range_filters,
        )
        .group_by(product_group_id)
        .order_by(func.sum(models.OrderItem.quantity).desc())
        .limit(10)
        .all()
    )

    revenue_range = (
        db.query(func.coalesce(func.sum(models.Payment.amount_cents), 0))
        .filter(
            models.Payment.tenant_id == tenant_id,
            payment_ok,
            order_ok,
            *range_filters,
        )
        .join(models.Order, models.Order.id == models.Payment.order_id)
        .scalar()
        or 0
    )

    total_qty = (
        db.query(func.coalesce(func.sum(models.OrderItem.quantity), 0))
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .join(models.Payment, models.Payment.order_id == models.Order.id)
        .filter(
            models.OrderItem.tenant_id == tenant_id,
            models.Payment.tenant_id == tenant_id,
            payment_ok,
            order_ok,
            *range_filters,
        )
        .scalar()
        or 0
    )

    month_bucket = func.date_trunc("month", models.Payment.created_at).label("month_bucket")
    revenue_by_month_rows = (
        db.query(
            month_bucket,
            func.coalesce(func.sum(models.Payment.amount_cents), 0).label("revenue_cents"),
        )
        .join(models.Order, models.Order.id == models.Payment.order_id)
        .filter(
            models.Payment.tenant_id == tenant_id,
            payment_ok,
            order_ok,
            *range_filters,
        )
        .group_by(month_bucket)
        .order_by(month_bucket.asc())
        .all()
    )

    total_orders = (
        db.query(func.count(func.distinct(models.Order.id)))
        .join(models.Payment, models.Payment.order_id == models.Order.id)
        .filter(
            models.Order.tenant_id == tenant_id,
            models.Payment.tenant_id == tenant_id,
            payment_ok,
            order_ok,
            *range_filters,
        )
        .scalar()
        or 0
    )

    customer_label = func.coalesce(models.Customer.name, models.Customer.phone, "Cliente").label("customer_name")
    top_customers = (
        db.query(
            customer_label,
            func.coalesce(func.sum(models.Payment.amount_cents), 0).label("revenue_cents"),
        )
        .join(models.Order, models.Order.id == models.Payment.order_id)
        .join(models.Customer, models.Customer.id == models.Order.customer_id)
        .filter(
            models.Payment.tenant_id == tenant_id,
            models.Order.tenant_id == tenant_id,
            models.Customer.tenant_id == tenant_id,
            payment_ok,
            order_ok,
            *range_filters,
        )
        .group_by(customer_label)
        .order_by(func.sum(models.Payment.amount_cents).desc())
        .limit(10)
        .all()
    )

    local_created_at = func.timezone("America/Sao_Paulo", models.Payment.created_at)
    day_bucket = func.date_trunc("day", local_created_at).label("day_bucket")
    daily_sales = (
        db.query(
            day_bucket,
            func.coalesce(func.sum(models.Payment.amount_cents), 0).label("revenue_cents"),
        )
        .join(models.Order, models.Order.id == models.Payment.order_id)
        .filter(
            models.Payment.tenant_id == tenant_id,
            models.Order.tenant_id == tenant_id,
            payment_ok,
            order_ok,
            *range_filters,
        )
        .group_by(day_bucket)
        .subquery()
    )
    weekday_rows = (
        db.query(
            func.extract("dow", daily_sales.c.day_bucket).label("dow"),
            func.count().label("days_with_sales"),
            func.coalesce(func.sum(daily_sales.c.revenue_cents), 0).label("total_cents"),
            func.coalesce(func.avg(daily_sales.c.revenue_cents), 0).label("avg_cents"),
        )
        .group_by("dow")
        .order_by("dow")
        .all()
    )

    min_max = db.query(
        func.min(daily_sales.c.day_bucket),
        func.max(daily_sales.c.day_bucket),
    ).first()
    start_for_counts = range_start
    end_for_counts = range_end
    if not start_for_counts or not end_for_counts:
        min_day = min_max[0] if min_max else None
        max_day = min_max[1] if min_max else None
        if min_day and max_day:
            start_for_counts = min_day
            end_for_counts = max_day
        else:
            start_for_counts = now
            end_for_counts = now

    start_date_local = start_for_counts.astimezone(tz_sp).date()
    end_date_local = end_for_counts.astimezone(tz_sp).date()
    total_days_by_weekday = {idx: 0 for idx in range(7)}
    total_days_by_week_bucket = {idx: 0 for idx in range(1, 5)}
    cursor = start_date_local
    while cursor <= end_date_local:
        dow = (cursor.weekday() + 1) % 7
        total_days_by_weekday[dow] += 1
        week_bucket_value = 1 if cursor.day <= 7 else (2 if cursor.day <= 14 else (3 if cursor.day <= 21 else 4))
        total_days_by_week_bucket[week_bucket_value] += 1
        cursor += timedelta(days=1)

    weekday_labels = ["Domingo", "Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado"]
    weekday_stats_map = {int(row.dow): row for row in weekday_rows}
    avg_by_weekday = []
    for idx in range(7):
        row = weekday_stats_map.get(idx)
        total_cents = int(getattr(row, "total_cents", 0) or 0)
        days_with_sales = int(getattr(row, "days_with_sales", 0) or 0)
        total_days = total_days_by_weekday.get(idx, 0)
        avg_cents = int(getattr(row, "avg_cents", 0) or 0)
        avg_including_zero = int(total_cents / total_days) if total_days > 0 else 0
        avg_by_weekday.append(
            schemas.InsightAverageItem(
                name=weekday_labels[idx],
                avg_cents=avg_cents,
                avg_including_zero_cents=avg_including_zero,
                total_cents=total_cents,
                days_with_sales=days_with_sales,
                total_days=total_days,
            )
        )

    day_of_month = func.extract("day", daily_sales.c.day_bucket)
    week_bucket = case(
        (day_of_month <= 7, 1),
        (day_of_month <= 14, 2),
        (day_of_month <= 21, 3),
        else_=4,
    ).label("week_bucket")
    week_rows = (
        db.query(
            week_bucket,
            func.count().label("days_with_sales"),
            func.coalesce(func.sum(daily_sales.c.revenue_cents), 0).label("total_cents"),
            func.coalesce(func.avg(daily_sales.c.revenue_cents), 0).label("avg_cents"),
        )
        .group_by(week_bucket)
        .order_by(week_bucket)
        .all()
    )
    week_stats_map = {int(row.week_bucket): row for row in week_rows}
    avg_by_week_of_month = []
    for idx in range(1, 5):
        row = week_stats_map.get(idx)
        total_cents = int(getattr(row, "total_cents", 0) or 0)
        days_with_sales = int(getattr(row, "days_with_sales", 0) or 0)
        total_days = total_days_by_week_bucket.get(idx, 0)
        avg_cents = int(getattr(row, "avg_cents", 0) or 0)
        avg_including_zero = int(total_cents / total_days) if total_days > 0 else 0
        avg_by_week_of_month.append(
            schemas.InsightAverageItem(
                name=f"Semana {idx}",
                avg_cents=avg_cents,
                avg_including_zero_cents=avg_including_zero,
                total_cents=total_cents,
                days_with_sales=days_with_sales,
                total_days=total_days,
            )
        )

    return schemas.InsightsOut(
        revenue_today_cents=revenue_today,
        revenue_week_cents=revenue_week,
        revenue_month_cents=revenue_month,
        by_category=[
            schemas.InsightBreakdownItem(name=row.category_name, revenue_cents=int(row.revenue_cents or 0))
            for row in by_category
        ],
        by_store=[
            schemas.InsightBreakdownItem(name=row.store_name, revenue_cents=int(row.revenue_cents or 0))
            for row in by_store
        ],
        by_product=[
            schemas.InsightBreakdownItem(name=row.product_name, revenue_cents=int(row.revenue_cents or 0))
            for row in by_product
        ],
        revenue_range_cents=int(revenue_range),
        revenue_by_month=[
            schemas.InsightBreakdownItem(
                name=row.month_bucket.strftime("%Y-%m"),
                revenue_cents=int(row.revenue_cents or 0),
            )
            for row in revenue_by_month_rows
        ],
        by_product_quantity=[
            schemas.InsightBreakdownItem(name=row.product_name, revenue_cents=int(row.qty or 0))
            for row in qty_by_product
        ],
        top_customers=[
            schemas.InsightBreakdownItem(name=row.customer_name, revenue_cents=int(row.revenue_cents or 0))
            for row in top_customers
        ],
        avg_by_weekday=avg_by_weekday,
        avg_by_week_of_month=avg_by_week_of_month,
        total_quantity=int(total_qty),
        total_orders=int(total_orders),
        orders_today=int(orders_today),
        orders_month=int(orders_month),
    )
