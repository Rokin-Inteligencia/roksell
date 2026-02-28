"""
Serviço de checkout: lógica de negócio e persistência de criação de pedido e preview.
O router de checkout deve apenas orquestrar (validar request, chamar este serviço, disparar notificações).
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, date, timezone
from typing import Dict

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.domain.core.enums import CampaignType
from app.domain.config.order_statuses import default_order_status, load_order_statuses
from app.domain.shipping.store_calendar import load_store_closed_dates
from app.domain.shipping.store_hours import load_store_operating_hours
from app.domain.shipping.store_timezone import tzinfo_for_store
from app.domain.config.payment_methods import load_payment_methods
from app.domain.config.shipping_method import load_shipping_method
from app.domain.catalog.availability import is_available_for_sale
from app.security import create_order_tracking_token
from app.phone import normalize_phone, phone_candidates
from app.services.shipping_distance import (
    distance_from_store,
    shipping_override_for_postal_code,
    tier_amount_for_km,
)


def _gen_id() -> str:
    return str(uuid.uuid4())


def _normalize_postal_code(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return None
    return digits[:8]


def _format_address_for_shipping(addr: schemas.AddressIn | None) -> str | None:
    if not addr:
        return None
    parts: list[str] = []
    street = (addr.street or "").strip()
    number = (addr.number or "").strip()
    if street:
        parts.append(f"{street}, {number}" if number else street)
    district = (addr.district or "").strip()
    if district:
        parts.append(district)
    city = (addr.city or "").strip()
    state = (addr.state or "").strip()
    if city:
        parts.append(f"{city} - {state}" if state else city)
    postal = (_normalize_postal_code(addr.postal_code) or "").strip()
    if postal:
        parts.append(postal)
    parts.append("Brasil")
    output = ", ".join(p for p in parts if p)
    return output or None


def _compute_shipping_cents(
    *,
    db: Session,
    tenant_id: str,
    store: models.Store,
    payload: schemas.CheckoutIn,
) -> int | None:
    if payload.pickup:
        return 0
    if load_shipping_method(getattr(store, "shipping_method", None)) != "distance":
        raise HTTPException(400, "Metodo de frete nao suportado")
    if not payload.address:
        raise HTTPException(400, "Address required for delivery")

    override = shipping_override_for_postal_code(db, tenant_id, payload.address.postal_code)
    if override is not None:
        return int(override)

    dest_address = _format_address_for_shipping(payload.address)
    km = asyncio.run(
        distance_from_store(
            db,
            tenant_id=tenant_id,
            store_id=store.id,
            dest_address=dest_address,
        )
    )
    if km is None:
        return None
    amount = tier_amount_for_km(db, tenant_id, km, store_id=store.id)
    if amount is None:
        return None
    fixed_fee = int(getattr(store, "shipping_fixed_fee_cents", 0) or 0)
    return int(amount) + fixed_fee


def _campaign_discount(
    campaign: models.Campaign,
    subtotal_cents: int,
    shipping_cents: int,
    items: list[dict],
) -> int:
    if campaign.min_order_cents is not None and subtotal_cents < campaign.min_order_cents:
        return 0
    if campaign.usage_limit is not None and campaign.usage_count >= campaign.usage_limit:
        return 0

    value = campaign.value_percent
    if campaign.type == CampaignType.order_percent:
        base = subtotal_cents
    elif campaign.type == CampaignType.shipping_percent:
        base = shipping_cents
        if base <= 0:
            return 0
    elif campaign.type == CampaignType.category_percent:
        base = sum(
            item["amount_cents"]
            for item in items
            if item.get("category_id") == campaign.category_id
        )
        if base <= 0:
            return 0
    else:
        return 0

    discount = (base * value) // 100
    max_allowed = subtotal_cents + shipping_cents
    return int(min(discount, max_allowed))


def _normalize_operator(op: str | None) -> str:
    value = (op or "").strip().lower()
    mapping = {
        "=": "eq", "==": "eq", "igual": "eq",
        "!=": "neq", "diferente": "neq",
        ">": "gt", "maior": "gt", ">=": "gte", "maior_ou_igual": "gte",
        "<": "lt", "menor": "lt", "<=": "lte", "menor_ou_igual": "lte",
        "in": "in", "em": "in", "contains": "contains", "contem": "contains", "cont?m": "contains",
    }
    return mapping.get(value, value)


def _compare_numeric(lhs: int | float, rhs: int | float, op: str) -> bool:
    if op == "eq": return lhs == rhs
    if op == "neq": return lhs != rhs
    if op == "gt": return lhs > rhs
    if op == "gte": return lhs >= rhs
    if op == "lt": return lhs < rhs
    if op == "lte": return lhs <= rhs
    return False


def _rule_condition_met(cond: dict, context: dict) -> bool:
    dimension = (cond.get("dimension") or "").strip().lower()
    op = _normalize_operator(cond.get("operator"))
    value = cond.get("value")
    values = cond.get("values") if isinstance(cond.get("values"), list) else None
    product_id = cond.get("product_id")
    category_id = cond.get("category_id")

    if dimension == "quantidade_total":
        return _compare_numeric(context.get("total_qty", 0), int(value or 0), op)
    if dimension == "quantidade_produto" and product_id:
        qty = context.get("qty_by_product", {}).get(product_id, 0)
        return _compare_numeric(qty, int(value or 0), op)
    if dimension == "produto":
        if product_id:
            return context.get("qty_by_product", {}).get(product_id, 0) > 0
        if values:
            return any(context.get("qty_by_product", {}).get(pid, 0) > 0 for pid in values)
        return False
    if dimension == "categoria":
        if category_id:
            return context.get("qty_by_category", {}).get(category_id, 0) > 0
        if values:
            return any(context.get("qty_by_category", {}).get(cid, 0) > 0 for cid in values)
        return False
    if dimension == "valor_total":
        return _compare_numeric(context.get("total_cents", 0), int(value or 0), op)
    if dimension == "tipo_entrega":
        delivery_type = "retirada" if context.get("pickup") else "entrega"
        target = (str(value or "").strip().lower() or "")
        if op in {"eq", "contains"}:
            return delivery_type == target
        if op == "neq":
            return delivery_type != target
        return False
    if dimension == "cliente":
        customer_id = context.get("customer_id")
        if values:
            return customer_id in values
        return customer_id == value
    return False


def _apply_rule_action(action: dict, context: dict, result: dict) -> None:
    action_type = (action.get("type") or "").strip().lower()
    value_cents = int(action.get("value_cents") or 0)
    value_percent = int(action.get("value_percent") or 0)
    product_id = action.get("product_id")
    category_id = action.get("category_id")
    gift_qty = int(action.get("gift_qty") or 1)

    if action_type == "frete_gratis":
        result["shipping_cents"] = 0
    elif action_type == "frete_maximo" and value_cents >= 0:
        result["shipping_cents"] = min(result["shipping_cents"], value_cents)
    elif action_type == "frete_desconto" and value_cents > 0:
        result["shipping_cents"] = max(0, result["shipping_cents"] - value_cents)
    elif action_type == "desconto_total_percentual" and value_percent > 0:
        result["discount_cents"] += (context["subtotal_cents"] * value_percent) // 100
    elif action_type == "desconto_total_fixo" and value_cents > 0:
        result["discount_cents"] += value_cents
    elif action_type == "desconto_item_percentual" and product_id and value_percent > 0:
        amount = sum(i["amount_cents"] for i in context["items"] if i.get("product_id") == product_id)
        result["discount_cents"] += (amount * value_percent) // 100
    elif action_type == "desconto_item_fixo" and product_id and value_cents > 0:
        result["discount_cents"] += value_cents * context["qty_by_product"].get(product_id, 0)
    elif action_type == "desconto_categoria_percentual" and category_id and value_percent > 0:
        amount = sum(i["amount_cents"] for i in context["items"] if i.get("category_id") == category_id)
        result["discount_cents"] += (amount * value_percent) // 100
    elif action_type == "desconto_categoria_fixo" and category_id and value_cents > 0:
        result["discount_cents"] += value_cents * context["qty_by_category"].get(category_id, 0)
    elif action_type == "brinde_produto" and product_id and gift_qty > 0:
        result["gift_items"].append({"product_id": product_id, "quantity": gift_qty})


def _evaluate_rule_campaign(campaign: models.Campaign, context: dict) -> dict | None:
    if not campaign.rule_config:
        return None
    try:
        rule_config = json.loads(campaign.rule_config)
    except json.JSONDecodeError:
        return None
    rules = rule_config.get("rules")
    if not isinstance(rules, list) or not rules:
        return None

    result = {"shipping_cents": context["shipping_cents"], "discount_cents": 0, "gift_items": [], "applied": False}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        conditions = rule.get("conditions") or []
        if not isinstance(conditions, list) or not conditions:
            continue
        logic = (rule.get("conditions_logic") or "E").strip().upper()
        if logic not in {"E", "OU"}:
            logic = "E"
        matches = [_rule_condition_met(c, context) for c in conditions if isinstance(c, dict)]
        is_match = all(matches) if logic == "E" else any(matches)
        if not is_match:
            continue
        action = rule.get("action")
        if isinstance(action, dict):
            _apply_rule_action(action, context, result)
            result["applied"] = True
        if rule.get("stop_on_match"):
            break
        if campaign.apply_mode == "first" and result["applied"]:
            break
    return result if result["applied"] else None


def _pick_campaigns_and_apply(
    db: Session,
    campaigns: list[models.Campaign],
    subtotal_cents: int,
    shipping_cents: int,
    items: list[dict],
    coupon_required: bool,
    store_id: str | None,
    pickup: bool,
    customer_id: str | None,
) -> tuple[list[models.Campaign], int, int, list[dict]]:
    applied_campaigns: list[models.Campaign] = []
    total_discount = 0
    current_shipping = shipping_cents
    gift_items: list[dict] = []

    qty_by_product = {}
    qty_by_category = {}
    total_qty = 0
    for item in items:
        qty = int(item.get("quantity") or 0)
        total_qty += qty
        pid = item.get("product_id")
        if pid:
            qty_by_product[pid] = qty_by_product.get(pid, 0) + qty
        cid = item.get("category_id")
        if cid:
            qty_by_category[cid] = qty_by_category.get(cid, 0) + qty

    context = {
        "subtotal_cents": subtotal_cents,
        "shipping_cents": current_shipping,
        "items": items,
        "qty_by_product": qty_by_product,
        "qty_by_category": qty_by_category,
        "total_qty": total_qty,
        "total_cents": subtotal_cents + current_shipping,
        "pickup": pickup,
        "customer_id": customer_id,
    }

    has_coupon_campaign = any(c.coupon_code for c in campaigns)
    for campaign in campaigns:
        if campaign.usage_limit is not None and campaign.usage_count >= campaign.usage_limit:
            continue
        store_ok = True
        if store_id:
            store_rows = (
                db.query(models.CampaignStore.store_id)
                .filter(
                    models.CampaignStore.tenant_id == campaign.tenant_id,
                    models.CampaignStore.campaign_id == campaign.id,
                )
                .all()
            )
            store_ids = [r[0] for r in store_rows]
            if store_ids and store_id not in store_ids:
                store_ok = False
        if not store_ok:
            continue

        if campaign.type == CampaignType.rule:
            context["shipping_cents"] = current_shipping
            context["total_cents"] = subtotal_cents + current_shipping
            rule_result = _evaluate_rule_campaign(campaign, context)
            if rule_result:
                applied_campaigns.append(campaign)
                current_shipping = rule_result["shipping_cents"]
                total_discount += rule_result["discount_cents"]
                gift_items.extend(rule_result["gift_items"])
                if campaign.apply_mode == "first":
                    break
            continue

        discount = _campaign_discount(campaign, subtotal_cents, current_shipping, items)
        if discount > 0:
            applied_campaigns.append(campaign)
            total_discount += discount
            if campaign.apply_mode == "first":
                break

    if coupon_required and has_coupon_campaign and not applied_campaigns:
        raise HTTPException(400, "Cupom inválido")

    max_allowed = subtotal_cents + current_shipping
    total_discount = int(min(total_discount, max_allowed))
    return applied_campaigns, total_discount, current_shipping, gift_items


def _get_store_or_default(db: Session, tenant_id: str, store_id: str | None) -> models.Store:
    query = db.query(models.Store).filter(models.Store.tenant_id == tenant_id, models.Store.is_active.is_(True))
    if store_id:
        store = query.filter(models.Store.id == store_id).first()
        if not store:
            raise HTTPException(404, "Loja não encontrada")
        return store
    store = query.order_by(models.Store.name.asc()).first()
    if not store:
        raise HTTPException(400, "Nenhuma loja ativa configurada")
    return store


def _load_payment_methods(db: Session, tenant_id: str, store: models.Store) -> list[str]:
    store_payment_methods = getattr(store, "payment_methods", None)
    if store_payment_methods:
        return load_payment_methods(store_payment_methods)
    cfg = (
        db.query(models.OperationsConfig)
        .filter(models.OperationsConfig.tenant_id == tenant_id)
        .first()
    )
    return load_payment_methods(cfg.payment_methods if cfg else None)


def _load_order_statuses(db: Session, tenant_id: str, store: models.Store) -> list[str]:
    store_order_statuses = getattr(store, "order_statuses", None)
    if store_order_statuses:
        return load_order_statuses(store_order_statuses)
    cfg = (
        db.query(models.OperationsConfig)
        .filter(models.OperationsConfig.tenant_id == tenant_id)
        .first()
    )
    return load_order_statuses(cfg.order_statuses if cfg else None)


def _validate_delivery_date_open(store: models.Store, delivery_date: date) -> None:
    allowed_dates = load_store_closed_dates(store.closed_dates)
    if allowed_dates and delivery_date not in allowed_dates:
        raise HTTPException(400, "Data de entrega indisponível para a loja")
    operating_hours = load_store_operating_hours(store.operating_hours)
    if not operating_hours:
        return
    weekday = int(delivery_date.weekday())
    day_entry = next((item for item in operating_hours if int(item.get("day", -1)) == weekday), None)
    if not day_entry or not day_entry.get("enabled"):
        raise HTTPException(400, "Loja fechada no dia selecionado")


def _store_open_now(store: models.Store) -> bool:
    now = datetime.now(timezone.utc).astimezone(tzinfo_for_store(store))
    today = now.date()
    allowed_dates = load_store_closed_dates(store.closed_dates)
    if allowed_dates and today not in allowed_dates:
        return False
    operating_hours = load_store_operating_hours(store.operating_hours)
    if not operating_hours:
        return True
    weekday = int(today.weekday())
    day_entry = next((item for item in operating_hours if int(item.get("day", -1)) == weekday), None)
    if not day_entry or not day_entry.get("enabled"):
        return False
    open_time = str(day_entry.get("open") or "").strip()
    close_time = str(day_entry.get("close") or "").strip()
    if not open_time or not close_time:
        return False
    try:
        open_hour, open_minute = [int(x) for x in open_time.split(":", 1)]
        close_hour, close_minute = [int(x) for x in close_time.split(":", 1)]
    except ValueError:
        return False
    open_minutes = open_hour * 60 + open_minute
    close_minutes = close_hour * 60 + close_minute
    now_minutes = now.hour * 60 + now.minute
    return open_minutes <= now_minutes < close_minutes


def _store_today(store: models.Store):
    return datetime.now(timezone.utc).astimezone(tzinfo_for_store(store)).date()


def _store_open_on_date(store: models.Store, target_date) -> bool:
    allowed_dates = load_store_closed_dates(store.closed_dates)
    if allowed_dates and target_date not in allowed_dates:
        return False
    operating_hours = load_store_operating_hours(store.operating_hours)
    if not operating_hours:
        return True
    weekday = int(target_date.weekday())
    day_entry = next((item for item in operating_hours if int(item.get("day", -1)) == weekday), None)
    return bool(day_entry and day_entry.get("enabled"))


def _next_store_open_date(store: models.Store, start_date, max_days: int = 90):
    for offset in range(max_days + 1):
        candidate = start_date + timedelta(days=offset)
        if _store_open_on_date(store, candidate):
            return candidate
    return None


def _load_campaigns_for_checkout(
    db: Session,
    tenant_id: str,
    coupon_code: str | None,
) -> list[models.Campaign]:
    now = datetime.now(timezone.utc)
    query = (
        db.query(models.Campaign)
        .filter(models.Campaign.tenant_id == tenant_id)
        .filter(models.Campaign.is_active.is_(True))
        .filter(or_(models.Campaign.starts_at.is_(None), models.Campaign.starts_at <= now))
        .filter(or_(models.Campaign.ends_at.is_(None), models.Campaign.ends_at >= now))
    )
    if coupon_code:
        query = query.filter(models.Campaign.coupon_code.ilike(coupon_code.strip()))
    else:
        query = query.filter(or_(models.Campaign.coupon_code.is_(None), models.Campaign.coupon_code == ""))
    return query.order_by(models.Campaign.priority.asc(), models.Campaign.created_at.desc()).all()


def _custom_item_price(item: schemas.ItemIn) -> int:
    return int(item.custom_price_cents or 0)


def _normalize_item_note(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def _normalize_additional_ids(item: schemas.ItemIn) -> list[str]:
    unique_ids: list[str] = []
    seen: set[str] = set()
    for raw in item.additional_ids or []:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        unique_ids.append(value)
    return unique_ids


def _resolve_item_additionals(
    db: Session,
    tenant_id: str,
    store_id: str,
    product: models.Product,
    item: schemas.ItemIn,
) -> tuple[int, list[models.Additional]]:
    selected_ids = _normalize_additional_ids(item)
    if not selected_ids:
        return 0, []
    if product.is_custom:
        raise HTTPException(400, "Custom item cannot include additionals")
    if not product.additionals_enabled:
        raise HTTPException(400, f"Additionals are disabled for product: {item.product_id}")

    allowed_ids = {link.additional_id for link in (product.additional_links or [])}
    invalid_ids = [aid for aid in selected_ids if aid not in allowed_ids]
    if invalid_ids:
        raise HTTPException(400, f"Invalid additional for product: {invalid_ids[0]}")

    rows = (
        db.query(models.Additional)
        .filter(
            models.Additional.tenant_id == tenant_id,
            models.Additional.is_active.is_(True),
            models.Additional.id.in_(selected_ids),
            or_(models.Additional.store_id == store_id, models.Additional.store_id.is_(None)),
        )
        .all()
    )
    by_id = {row.id: row for row in rows}
    ordered_rows = [by_id[aid] for aid in selected_ids if aid in by_id]
    if len(ordered_rows) != len(selected_ids):
        raise HTTPException(400, "One or more additionals are unavailable for this store")
    additional_total = sum(int(row.price_cents or 0) for row in ordered_rows)
    return additional_total, ordered_rows


def _unit_price_for_item(item: schemas.ItemIn, product: models.Product, additional_total_cents: int = 0) -> int:
    if product.is_custom:
        unit_price = _custom_item_price(item)
        if unit_price <= 0:
            raise HTTPException(400, f"Custom price required for {item.product_id}")
        return unit_price
    return int(product.price_cents or 0) + int(additional_total_cents or 0)


def _compose_item_notes(
    item: schemas.ItemIn, product: models.Product, additionals: list[models.Additional]
) -> str | None:
    details: list[str] = []
    if additionals:
        names = ", ".join(a.name for a in additionals if a.name)
        if names:
            details.append(f"Adicionais: {names}")
    item_note = _normalize_item_note(item.item_notes)
    if item_note:
        details.append(f"Obs: {item_note}")
    if product.is_custom:
        if item.custom_name:
            details.append(f"Nome: {item.custom_name}")
        if item.custom_description:
            details.append(f"Descricao: {item.custom_description}")
        if item.custom_weight:
            details.append(f"Peso: {item.custom_weight}")
    return " | ".join(details) if details else None


def _calc_subtotal_and_items(
    db: Session, tenant_id: str, store_id: str, items: list[schemas.ItemIn]
) -> tuple[int, list[dict], dict[str, models.Product], list[dict]]:
    subtotal = 0
    item_amounts: list[dict] = []
    item_details: list[dict] = []
    products_cache: Dict[str, models.Product] = {}
    for item in items:
        product = (
            db.query(models.Product)
            .options(selectinload(models.Product.additional_links))
            .filter(
                models.Product.id == item.product_id,
                models.Product.tenant_id == tenant_id,
                models.Product.is_active.is_(True),
                or_(models.Product.store_id == store_id, models.Product.store_id.is_(None)),
            )
            .first()
        )
        if not product:
            raise HTTPException(400, f"Invalid product: {item.product_id}")
        if not is_available_for_sale(
            getattr(product, "availability_status", None),
            getattr(product, "block_sale", None),
        ):
            raise HTTPException(400, f"Product not available for online sale: {item.product_id}")
        additional_total, selected_additionals = _resolve_item_additionals(db, tenant_id, store_id, product, item)
        unit_price = _unit_price_for_item(item, product, additional_total)
        note_text = _compose_item_notes(item, product, selected_additionals)
        products_cache[item.product_id] = product
        subtotal += unit_price * item.quantity
        item_amounts.append({
            "product_id": item.product_id,
            "category_id": product.category_id,
            "amount_cents": unit_price * item.quantity,
            "quantity": item.quantity,
            "unit_price_cents": unit_price,
        })
        item_details.append({
            "unit_price_cents": unit_price,
            "additional_names": [a.name for a in selected_additionals if a.name],
            "notes": note_text,
        })
    return subtotal, item_amounts, products_cache, item_details


def _reserve_stock(
    db: Session,
    tenant_id: str,
    store_id: str,
    items: list[schemas.ItemIn],
    products_cache: Dict[str, models.Product],
) -> None:
    insufficient: list[dict] = []
    reserved: list[tuple[schemas.ItemIn, models.StoreInventory | None, int]] = []
    for item in items:
        product = products_cache.get(item.product_id)
        if product and product.is_custom:
            continue
        inventory = (
            db.query(models.StoreInventory)
            .filter(
                models.StoreInventory.tenant_id == tenant_id,
                models.StoreInventory.store_id == store_id,
                models.StoreInventory.product_id == item.product_id,
            )
            .with_for_update()
            .first()
        )
        quantity = inventory.quantity if inventory else 0
        if quantity < item.quantity:
            name = product.name if product else item.product_id
            insufficient.append({
                "product_id": item.product_id,
                "product_name": name,
                "available": int(quantity or 0),
                "requested": int(item.quantity),
            })
        reserved.append((item, inventory, int(quantity or 0)))

    if insufficient:
        raise HTTPException(
            400,
            detail={
                "code": "INSUFFICIENT_STOCK",
                "message": "Estoque insuficiente para alguns produtos",
                "items": insufficient,
            },
        )

    for item, inventory, quantity in reserved:
        if inventory:
            inventory.quantity = quantity - item.quantity
        else:
            db.add(
                models.StoreInventory(
                    id=_gen_id(),
                    tenant_id=tenant_id,
                    store_id=store_id,
                    product_id=item.product_id,
                    quantity=max(quantity - item.quantity, 0),
                )
            )


# --- API pública ---


def preview_order(
    db: Session,
    tenant_id: str,
    payload: schemas.CheckoutPreviewIn,
) -> schemas.CheckoutPreviewOut:
    """Preview de pedido (subtotal, frete, desconto, total)."""
    if not payload.items:
        raise HTTPException(400, "Empty cart")

    store = _get_store_or_default(db, tenant_id, payload.store_id)
    subtotal, item_amounts, _, _ = _calc_subtotal_and_items(db, tenant_id, store.id, payload.items)
    shipping_cents = int(payload.shipping_cents or 0)
    coupon_code = (payload.coupon_code or "").strip().upper()

    campaigns = _load_campaigns_for_checkout(db, tenant_id, coupon_code or None)
    applied_campaigns, discount_cents, adjusted_shipping, _ = _pick_campaigns_and_apply(
        db=db,
        campaigns=campaigns,
        subtotal_cents=subtotal,
        shipping_cents=shipping_cents,
        items=item_amounts,
        coupon_required=bool(coupon_code),
        store_id=store.id,
        pickup=payload.pickup,
        customer_id=None,
    )

    total = max(subtotal + adjusted_shipping - discount_cents, 0)
    campaign = applied_campaigns[0] if applied_campaigns else None
    return schemas.CheckoutPreviewOut(
        subtotal_cents=subtotal,
        shipping_cents=adjusted_shipping,
        discount_cents=discount_cents,
        total_cents=total,
        campaign=campaign,
    )


@dataclass
class CheckoutResult:
    """Resultado de place_order para o router montar resposta e notificações."""
    order_id: str
    total_cents: int
    tracking_token: str
    tenant_id: str
    customer_name: str
    customer_phone: str
    pickup: bool
    address_text: str
    delivery_window_start: datetime | None
    delivery_window_end: datetime | None
    delivery_date: date
    notes: str | None
    items_payload: list[dict]
    payment_method: str
    subtotal_cents: int
    shipping_cents: int
    discount_cents: int


def place_order(db: Session, tenant_id: str, payload: schemas.CheckoutIn) -> CheckoutResult:
    """Executa todo o fluxo de criação de pedido: validações, estoque, persistência. Retorna dados para resposta e notificações."""
    if not payload.items:
        raise HTTPException(400, "Empty cart")

    store = _get_store_or_default(db, tenant_id, payload.store_id)
    store_open_now = _store_open_now(store)
    allow_preorder_when_closed = bool(getattr(store, "allow_preorder_when_closed", True))
    if not store_open_now and not allow_preorder_when_closed:
        raise HTTPException(400, "Loja fechada no momento e encomendas desabilitadas")
    if not store_open_now and allow_preorder_when_closed and not bool(payload.preorder_confirmed):
        local_today = _store_today(store)
        next_open_date = _next_store_open_date(store, local_today)
        raise HTTPException(
            409,
            detail={
                "code": "PREORDER_CONFIRM_REQUIRED",
                "message": "Loja fechada no momento. Confirme para enviar como encomenda.",
                "next_open_date": next_open_date.isoformat() if next_open_date else None,
            },
        )
    if not payload.pickup and not store.is_delivery:
        raise HTTPException(400, "Loja selecionada não aceita entregas")

    coupon_code = (payload.coupon_code or "").strip().upper()
    local_today = _store_today(store)
    delivery_date = payload.delivery_date or local_today
    if delivery_date < local_today:
        raise HTTPException(400, "Data de entrega inválida")
    _validate_delivery_date_open(store, delivery_date)

    normalized_phone = normalize_phone(payload.phone)
    if not normalized_phone:
        raise HTTPException(400, "Invalid phone")
    candidates = phone_candidates(payload.phone)
    if not candidates:
        candidates = [normalized_phone]
    customer = (
        db.query(models.Customer)
        .filter(
            models.Customer.tenant_id == tenant_id,
            models.Customer.phone.in_(candidates),
        )
        .first()
    )
    if not customer:
        customer = models.Customer(
            id=_gen_id(),
            tenant_id=tenant_id,
            origin_store_id=store.id,
            name=payload.name,
            phone=normalized_phone,
        )
        db.add(customer)
        db.flush()
    elif not customer.origin_store_id:
        customer.origin_store_id = store.id
    elif customer.phone != normalized_phone:
        existing = (
            db.query(models.Customer)
            .filter(
                models.Customer.tenant_id == tenant_id,
                models.Customer.phone == normalized_phone,
            )
            .first()
        )
        if not existing or existing.id == customer.id:
            customer.phone = normalized_phone

    address_id = None
    address_text = "(pickup at store)"
    shipping_cents_payload = int(payload.shipping_cents or 0)
    shipping_cents = 0
    if payload.pickup and shipping_cents_payload != 0:
        raise HTTPException(400, "Shipping must be zero for pickup orders")

    if not payload.pickup:
        if not payload.address:
            raise HTTPException(400, "Address required for delivery")
        addr = payload.address
        normalized_postal = _normalize_postal_code(addr.postal_code)
        if not normalized_postal or len(normalized_postal) != 8:
            raise HTTPException(400, "CEP inválido")
        address = models.CustomerAddress(
            id=_gen_id(),
            tenant_id=tenant_id,
            customer_id=customer.id,
            postal_code=normalized_postal,
            street=addr.street,
            number=addr.number,
            complement=addr.complement,
            district=addr.district,
            city=addr.city,
            state=addr.state,
            reference=addr.reference,
            is_preferred=True,
        )
        db.add(address)
        db.flush()
        address_id = address.id
        complement = f" ({addr.complement})" if addr.complement else ""
        reference = f" | Ref: {addr.reference}" if addr.reference else ""
        district = addr.district or ""
        postal_label = normalized_postal or (addr.postal_code or "")
        address_text = (
            f"{addr.street}, {addr.number}{complement}\n"
            f"{district} - {addr.city}/{addr.state}\n"
            f"CEP: {postal_label}{reference}"
        )
        computed_shipping = _compute_shipping_cents(db=db, tenant_id=tenant_id, store=store, payload=payload)
        if computed_shipping is not None:
            if computed_shipping != shipping_cents_payload:
                raise HTTPException(400, "Invalid shipping amount")
            shipping_cents = computed_shipping
        else:
            shipping_cents = shipping_cents_payload

    subtotal, item_amounts, products_cache, item_details = _calc_subtotal_and_items(
        db, tenant_id, store.id, payload.items
    )

    campaigns = _load_campaigns_for_checkout(db, tenant_id, coupon_code or None)
    applied_campaigns, discount_cents, adjusted_shipping, gift_items = _pick_campaigns_and_apply(
        db=db,
        campaigns=campaigns,
        subtotal_cents=subtotal,
        shipping_cents=shipping_cents,
        items=item_amounts,
        coupon_required=bool(coupon_code),
        store_id=store.id,
        pickup=payload.pickup,
        customer_id=customer.id,
    )

    for campaign in applied_campaigns:
        if campaign.usage_limit is not None and campaign.usage_count >= campaign.usage_limit:
            raise HTTPException(400, "Campanha esgotada")

    _reserve_stock(db, tenant_id, store.id, payload.items, products_cache)

    gift_payload_items: list[schemas.ItemIn] = []
    gift_products_cache: Dict[str, models.Product] = {}
    for gift in gift_items:
        product_id = gift.get("product_id")
        quantity = int(gift.get("quantity") or 0)
        if not product_id or quantity <= 0:
            continue
        product = (
            db.query(models.Product)
            .filter(
                models.Product.id == product_id,
                models.Product.tenant_id == tenant_id,
                models.Product.is_active.is_(True),
                or_(models.Product.store_id == store.id, models.Product.store_id.is_(None)),
            )
            .first()
        )
        if not product or not is_available_for_sale(
            getattr(product, "availability_status", None),
            getattr(product, "block_sale", None),
        ):
            continue
        gift_products_cache[product_id] = product
        gift_payload_items.append(schemas.ItemIn(product_id=product_id, quantity=quantity))

    if gift_payload_items:
        _reserve_stock(db, tenant_id, store.id, gift_payload_items, gift_products_cache)

    items_payload: list[dict] = []
    for idx, item in enumerate(payload.items):
        product = products_cache[item.product_id]
        detail = item_details[idx] if idx < len(item_details) else {"unit_price_cents": product.price_cents, "additional_names": []}
        display_name = item.custom_name or product.name or "Produto customizado"
        additional_names = detail.get("additional_names") or []
        if additional_names:
            display_name = f"{display_name} (+{', '.join(additional_names)})"
        items_payload.append({
            "name": display_name,
            "quantity": item.quantity,
            "unit_price_cents": int(detail.get("unit_price_cents") or 0),
        })

    for gift in gift_payload_items:
        product = gift_products_cache[gift.product_id]
        items_payload.append({
            "name": f"{product.name} (Brinde)",
            "quantity": gift.quantity,
            "unit_price_cents": 0,
        })

    total = max(subtotal + adjusted_shipping - discount_cents, 0)
    order_statuses = _load_order_statuses(db, tenant_id, store)
    order = models.Order(
        id=_gen_id(),
        tenant_id=tenant_id,
        customer_id=customer.id,
        address_id=address_id,
        subtotal_cents=subtotal,
        discount_cents=discount_cents,
        campaign_id=applied_campaigns[0].id if applied_campaigns else None,
        shipping_cents=adjusted_shipping,
        total_cents=total,
        delivery_date=delivery_date,
        status=default_order_status(order_statuses),
        delivery_window_start=payload.delivery_window_start,
        delivery_window_end=payload.delivery_window_end,
        notes=payload.notes,
        store_id=store.id,
    )
    db.add(order)
    db.flush()

    for campaign in applied_campaigns:
        campaign.usage_count += 1

    for idx, item in enumerate(payload.items):
        product = products_cache[item.product_id]
        detail = item_details[idx] if idx < len(item_details) else {}
        notes = detail.get("notes")
        db.add(
            models.OrderItem(
                id=_gen_id(),
                tenant_id=tenant_id,
                order_id=order.id,
                product_id=product.id,
                quantity=item.quantity,
                unit_price_cents=int(detail.get("unit_price_cents") or product.price_cents),
                notes=notes,
            )
        )

    for gift in gift_payload_items:
        product = gift_products_cache.get(gift.product_id)
        if not product:
            continue
        db.add(
            models.OrderItem(
                id=_gen_id(),
                tenant_id=tenant_id,
                order_id=order.id,
                product_id=product.id,
                quantity=gift.quantity,
                unit_price_cents=0,
                notes="BRINDE",
            )
        )

    method = payload.payment.method.lower()
    allowed_methods = _load_payment_methods(db, tenant_id, store)
    if method not in allowed_methods:
        raise HTTPException(400, "Payment method not available")

    payment = models.Payment(
        id=_gen_id(),
        tenant_id=tenant_id,
        order_id=order.id,
        method=models.PaymentMethod(method),
        status=models.PaymentStatus.pending,
        amount_cents=total,
    )
    db.add(payment)

    delivery = models.Delivery(
        id=_gen_id(),
        tenant_id=tenant_id,
        order_id=order.id,
        status=models.DeliveryStatus.pending,
    )
    db.add(delivery)

    db.commit()

    tracking_token = create_order_tracking_token(order.id, customer.phone or "")

    return CheckoutResult(
        order_id=order.id,
        total_cents=total,
        tracking_token=tracking_token,
        tenant_id=tenant_id,
        customer_name=customer.name or "Customer",
        customer_phone=customer.phone or "",
        pickup=bool(payload.pickup),
        address_text=address_text,
        delivery_window_start=payload.delivery_window_start,
        delivery_window_end=payload.delivery_window_end,
        delivery_date=delivery_date,
        notes=payload.notes,
        items_payload=items_payload,
        payment_method=payload.payment.method,
        subtotal_cents=subtotal,
        shipping_cents=shipping_cents,
        discount_cents=discount_cents,
    )
