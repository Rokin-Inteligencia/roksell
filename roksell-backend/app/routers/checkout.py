"""
Router de checkout: orquestra request/response e notificações em background.
Toda a lógica de negócio e persistência está em app.services.checkout.
"""
import logging
import os
from typing import Dict

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db, SessionLocal
from app.tenancy import TenantContext, get_tenant_context
from app.services.checkout import place_order, preview_order
from app.services.order_message import format_order_message
from app.services.webpush import send_order_push_notifications

router = APIRouter(prefix="/checkout", tags=["checkout"])
logger = logging.getLogger(__name__)


async def _send_telegram_message(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.info("Telegram send skipped: missing token/chat_id")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    timeouts = [10, 10, 10]
    backoffs = [0.5, 1.0]
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeouts[attempt]) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Telegram send failed (attempt %s) status=%s body=%s",
                attempt + 1,
                exc.response.status_code,
                exc.response.text,
            )
        except Exception:
            logger.exception("Failed to send Telegram message (attempt %s)", attempt + 1)
            if attempt < len(backoffs):
                import asyncio
                await asyncio.sleep(backoffs[attempt])
            else:
                return


async def _send_telegram_message_for_tenant(tenant_id: str, text: str) -> None:
    db = SessionLocal()
    try:
        module_enabled = (
            db.query(models.TenantModule)
            .filter(models.TenantModule.tenant_id == tenant_id, models.TenantModule.module == "messages")
            .first()
            is not None
        )
        if not module_enabled:
            logger.info("Telegram send skipped: messages module disabled for tenant=%s", tenant_id)
            return
        cfg = (
            db.query(models.OperationsConfig)
            .filter(models.OperationsConfig.tenant_id == tenant_id)
            .first()
        )
        if not cfg:
            logger.info("Telegram send skipped: missing config for tenant=%s", tenant_id)
            return
        enabled = bool(cfg.telegram_enabled) if cfg.telegram_enabled is not None else False
        token = cfg.telegram_bot_token
        chat_id = cfg.telegram_chat_id
        if not enabled:
            logger.info("Telegram send skipped: disabled for tenant=%s", tenant_id)
            return
        if not token or not chat_id:
            logger.info("Telegram send skipped: missing token/chat_id for tenant=%s", tenant_id)
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        timeouts = [10, 10, 10]
        backoffs = [0.5, 1.0]
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=timeouts[attempt]) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    return
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Telegram send failed (attempt %s) status=%s body=%s",
                    attempt + 1,
                    exc.response.status_code,
                    exc.response.text,
                )
            except Exception:
                logger.exception("Failed to send Telegram message (attempt %s)", attempt + 1)
                if attempt < len(backoffs):
                    import asyncio
                    await asyncio.sleep(backoffs[attempt])
                else:
                    return
    finally:
        db.close()


def _campaign_discount(
    campaign: models.Campaign,
    subtotal_cents: int,
    shipping_cents: int,
    items: list[dict],
) -> int:
    """Return discount in cents for a campaign; 0 when not applicable."""
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
        "=": "eq",
        "==": "eq",
        "igual": "eq",
        "!=": "neq",
        "diferente": "neq",
        ">": "gt",
        "maior": "gt",
        ">=": "gte",
        "maior_ou_igual": "gte",
        "<": "lt",
        "menor": "lt",
        "<=": "lte",
        "menor_ou_igual": "lte",
        "in": "in",
        "em": "in",
        "contains": "contains",
        "contem": "contains",
        "cont?m": "contains",
    }
    return mapping.get(value, value)


def _compare_numeric(lhs: int | float, rhs: int | float, op: str) -> bool:
    if op == "eq":
        return lhs == rhs
    if op == "neq":
        return lhs != rhs
    if op == "gt":
        return lhs > rhs
    if op == "gte":
        return lhs >= rhs
    if op == "lt":
        return lhs < rhs
    if op == "lte":
        return lhs <= rhs
    return False


def _rule_condition_met(cond: dict, context: dict) -> bool:
    dimension = (cond.get("dimension") or "").strip().lower()
    op = _normalize_operator(cond.get("operator"))
    value = cond.get("value")
    values = cond.get("values") if isinstance(cond.get("values"), list) else None
    product_id = cond.get("product_id")
    category_id = cond.get("category_id")

    if dimension == "quantidade_total":
        total_qty = context.get("total_qty", 0)
        return _compare_numeric(total_qty, int(value or 0), op)
    if dimension == "quantidade_produto":
        if not product_id:
            return False
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
        total_cents = context.get("total_cents", 0)
        return _compare_numeric(total_cents, int(value or 0), op)
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


def _apply_rule_action(
    action: dict,
    context: dict,
    result: dict,
) -> None:
    action_type = (action.get("type") or "").strip().lower()
    value_cents = int(action.get("value_cents") or 0)
    value_percent = int(action.get("value_percent") or 0)
    product_id = action.get("product_id")
    category_id = action.get("category_id")
    gift_qty = int(action.get("gift_qty") or 1)

    if action_type == "frete_gratis":
        result["shipping_cents"] = 0
        return
    if action_type == "frete_maximo":
        if value_cents >= 0:
            result["shipping_cents"] = min(result["shipping_cents"], value_cents)
        return
    if action_type == "frete_desconto":
        if value_cents > 0:
            result["shipping_cents"] = max(0, result["shipping_cents"] - value_cents)
        return
    if action_type == "desconto_total_percentual":
        if value_percent > 0:
            result["discount_cents"] += (context["subtotal_cents"] * value_percent) // 100
        return
    if action_type == "desconto_total_fixo":
        if value_cents > 0:
            result["discount_cents"] += value_cents
        return
    if action_type == "desconto_item_percentual" and product_id:
        if value_percent > 0:
            amount = sum(
                item["amount_cents"]
                for item in context["items"]
                if item.get("product_id") == product_id
            )
            result["discount_cents"] += (amount * value_percent) // 100
        return
    if action_type == "desconto_item_fixo" and product_id:
        if value_cents > 0:
            qty = context["qty_by_product"].get(product_id, 0)
            result["discount_cents"] += value_cents * qty
        return
    if action_type == "desconto_categoria_percentual" and category_id:
        if value_percent > 0:
            amount = sum(
                item["amount_cents"]
                for item in context["items"]
                if item.get("category_id") == category_id
            )
            result["discount_cents"] += (amount * value_percent) // 100
        return
    if action_type == "desconto_categoria_fixo" and category_id:
        if value_cents > 0:
            qty = context["qty_by_category"].get(category_id, 0)
            result["discount_cents"] += value_cents * qty
        return
    if action_type == "brinde_produto" and product_id:
        if gift_qty > 0:
            result["gift_items"].append({"product_id": product_id, "quantity": gift_qty})


def _evaluate_rule_campaign(
    campaign: models.Campaign,
    context: dict,
) -> dict | None:
    if not campaign.rule_config:
        return None
    try:
        rule_config = json.loads(campaign.rule_config)
    except json.JSONDecodeError:
        return None
    rules = rule_config.get("rules")
    if not isinstance(rules, list) or not rules:
        return None

    result = {
        "shipping_cents": context["shipping_cents"],
        "discount_cents": 0,
        "gift_items": [],
        "applied": False,
    }
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        conditions = rule.get("conditions") or []
        if not isinstance(conditions, list) or not conditions:
            continue
        logic = (rule.get("conditions_logic") or "E").strip().upper()
        if logic not in {"E", "OU"}:
            logic = "E"
        matches = []
        for cond in conditions:
            if not isinstance(cond, dict):
                continue
            matches.append(_rule_condition_met(cond, context))
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
        raise HTTPException(400, "Cupom inv?lido")

    max_allowed = subtotal_cents + current_shipping
    total_discount = int(min(total_discount, max_allowed))
    return applied_campaigns, total_discount, current_shipping, gift_items


def _get_store_or_default(db: Session, tenant_id: str, store_id: str | None) -> models.Store:
    query = db.query(models.Store).filter(models.Store.tenant_id == tenant_id, models.Store.is_active.is_(True))
    if store_id:
        store = query.filter(models.Store.id == store_id).first()
        if not store:
            raise HTTPException(404, "Loja nA£o encontrada")
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


def _validate_delivery_date_open(store: models.Store, delivery_date) -> None:
    allowed_dates = load_store_closed_dates(store.closed_dates)
    if allowed_dates and delivery_date not in allowed_dates:
        raise HTTPException(400, "Data de entrega indisponivel para a loja")

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
        open_hour, open_minute = [int(value) for value in open_time.split(":", 1)]
        close_hour, close_minute = [int(value) for value in close_time.split(":", 1)]
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
    return query.order_by(models.Campaign.created_at.desc()).all()


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
    invalid_ids = [additional_id for additional_id in selected_ids if additional_id not in allowed_ids]
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
    ordered_rows = [by_id[additional_id] for additional_id in selected_ids if additional_id in by_id]
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


def _compose_item_notes(item: schemas.ItemIn, product: models.Product, additionals: list[models.Additional]) -> str | None:
    details: list[str] = []
    if additionals:
        names = ", ".join(additional.name for additional in additionals if additional.name)
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
        item_amounts.append(
            {
                "product_id": item.product_id,
                "category_id": product.category_id,
                "amount_cents": unit_price * item.quantity,
                "quantity": item.quantity,
                "unit_price_cents": unit_price,
            }
        )
        item_details.append(
            {
                "unit_price_cents": unit_price,
                "additional_names": [additional.name for additional in selected_additionals if additional.name],
                "notes": note_text,
            }
        )
    return subtotal, item_amounts, products_cache, item_details


def _reserve_stock(
    db: Session,
    tenant_id: str,
    store_id: str,
    items: list[schemas.ItemIn],
    products_cache: Dict[str, models.Product],
):
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
            insufficient.append(
                {
                    "product_id": item.product_id,
                    "product_name": name,
                    "available": int(quantity or 0),
                    "requested": int(item.quantity),
                }
            )
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
            continue
        inventory = models.StoreInventory(
            id=gen_id(),
            tenant_id=tenant_id,
            store_id=store_id,
            product_id=item.product_id,
            quantity=max(quantity - item.quantity, 0),
        )
        db.add(inventory)


@router.post("/preview", response_model=schemas.CheckoutPreviewOut)
def preview_order_endpoint(
    payload: schemas.CheckoutPreviewIn,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return preview_order(db, tenant.id, payload)


@router.post("", response_model=schemas.OrderSummaryOut)
def create_order(
    payload: schemas.CheckoutIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    result = place_order(db, tenant.id, payload)

    background.add_task(
        send_order_push_notifications,
        [
            {
                "tenant_id": result.tenant_id,
                "order_id": result.order_id,
                "customer_name": result.customer_name,
                "total_cents": result.total_cents,
            }
        ],
    )

    message = format_order_message(
        order_id=result.order_id,
        customer_name=result.customer_name,
        phone=result.customer_phone,
        pickup=result.pickup,
        address_text=result.address_text,
        window_start=result.delivery_window_start.isoformat() if result.delivery_window_start else None,
        window_end=result.delivery_window_end.isoformat() if result.delivery_window_end else None,
        delivery_date=result.delivery_date.isoformat(),
        items=result.items_payload,
        payment_method=result.payment_method,
        subtotal_cents=result.subtotal_cents,
        shipping_cents=result.shipping_cents,
        discount_cents=result.discount_cents,
        total_cents=result.total_cents,
    )
    background.add_task(_send_telegram_message_for_tenant, result.tenant_id, message)

    return {
        "order_id": result.order_id,
        "total_cents": result.total_cents,
        "tracking_token": result.tracking_token,
    }
