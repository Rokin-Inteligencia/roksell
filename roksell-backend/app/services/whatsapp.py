from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app import models
from app.db import SessionLocal
from app.phone import normalize_phone, phone_candidates
from app.services.order_message import (
    format_money,
    format_order_message,
    format_order_status_message,
    format_status_items,
    render_template,
)

logger = logging.getLogger(__name__)
WHATSAPP_WINDOW_HOURS = int(os.getenv("WHATSAPP_WINDOW_HOURS", "24"))
ORDER_STATUS_LABELS_PT = {
    "received": "Recebido",
    "confirmed": "Confirmado",
    "preparing": "Preparando",
    "ready": "Pronto",
    "on_route": "A caminho",
    "delivered": "Entregue",
    "completed": "Concluido",
    "canceled": "Cancelado",
    "cancelled": "Cancelado",
}


def _whatsapp_window_open(db: Session, *, tenant_id: str, phone: str) -> bool:
    candidates = phone_candidates(phone)
    if not candidates:
        return False
    contact = (
        db.query(models.WhatsAppConversation)
        .filter(models.WhatsAppConversation.tenant_id == tenant_id)
        .filter(models.WhatsAppConversation.phone.in_(candidates))
        .order_by(models.WhatsAppConversation.last_inbound_at.desc())
        .first()
    )
    if not contact or not contact.last_inbound_at:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=WHATSAPP_WINDOW_HOURS)
    return contact.last_inbound_at >= cutoff


def _coerce_status_text(value: object | None) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        value = value.value
    return str(value)


def _status_label_pt(value: str) -> str:
    key = (value or "").strip().lower()
    key = key.replace("-", "_").replace(" ", "_")
    return ORDER_STATUS_LABELS_PT.get(key, value)


def _build_address_text(address: models.CustomerAddress | None, pickup: bool) -> str:
    if pickup:
        return "(pickup at store)"
    if not address:
        return "-"
    complement = f" ({address.complement})" if address.complement else ""
    reference = f" | Ref: {address.reference}" if address.reference else ""
    district = address.district or ""
    return (
        f"{address.street}, {address.number}{complement}\n"
        f"{district} - {address.city}/{address.state}\n"
        f"CEP: {address.postal_code}{reference}"
    )


def _build_store_address_text(store: models.Store | None) -> str:
    if not store:
        return "Retirada na loja"
    complement = f" ({store.complement})" if store.complement else ""
    reference = f" | Ref: {store.reference}" if store.reference else ""
    line1_parts = [p for p in [store.street, store.number] if p]
    line1 = ", ".join(line1_parts)
    if line1:
        line1 = f"{line1}{complement}"
    elif store.complement:
        line1 = store.complement
    district = store.district or ""
    city_state = "/".join([p for p in [store.city, store.state] if p])
    line2 = ""
    if district and city_state:
        line2 = f"{district} - {city_state}"
    elif district:
        line2 = district
    elif city_state:
        line2 = city_state
    line3 = f"CEP: {store.postal_code}{reference}" if store.postal_code else ""
    lines = [store.name] if store.name else []
    for line in [line1, line2, line3]:
        if line:
            lines.append(line)
    return "\n".join(lines) if lines else "Retirada na loja"


def _build_status_address_text(
    address: models.CustomerAddress | None,
    store: models.Store | None,
    pickup: bool,
) -> str:
    if pickup:
        return _build_store_address_text(store)
    if not address:
        return "-"
    complement = f" ({address.complement})" if address.complement else ""
    reference = f" | Ref: {address.reference}" if address.reference else ""
    district = address.district or ""
    return (
        f"{address.street}, {address.number}{complement}\n"
        f"{district} - {address.city}/{address.state}\n"
        f"CEP: {address.postal_code}{reference}"
    )


def build_order_status_message(
    db: Session,
    *,
    order: models.Order,
    status: str | None = None,
    customer: models.Customer | None = None,
) -> str:
    status_text = _coerce_status_text(status if status is not None else getattr(order, "status", ""))
    status_text = (status_text or "").strip() or "atualizado"
    status_text = _status_label_pt(status_text)
    customer_record = customer
    if customer_record is None:
        customer_record = (
            db.query(models.Customer)
            .filter(models.Customer.id == order.customer_id, models.Customer.tenant_id == order.tenant_id)
            .first()
        )
    customer_name = customer_record.name if customer_record and customer_record.name else "Cliente"

    address = None
    if order.address_id:
        address = (
            db.query(models.CustomerAddress)
            .filter(
                models.CustomerAddress.id == order.address_id,
                models.CustomerAddress.tenant_id == order.tenant_id,
            )
            .first()
        )
    store = None
    if order.store_id:
        store = (
            db.query(models.Store)
            .filter(models.Store.id == order.store_id, models.Store.tenant_id == order.tenant_id)
            .first()
        )
    items_rows = (
        db.query(models.OrderItem, models.Product)
        .join(models.Product, models.Product.id == models.OrderItem.product_id)
        .filter(
            models.OrderItem.order_id == order.id,
            models.OrderItem.tenant_id == order.tenant_id,
            models.Product.tenant_id == order.tenant_id,
        )
        .all()
    )
    items_payload = [
        {
            "name": product.name,
            "quantity": item.quantity,
            "unit_price_cents": item.unit_price_cents,
        }
        for (item, product) in items_rows
    ]

    pickup = not bool(order.address_id)
    address_text = _build_status_address_text(address, store, pickup)
    shipping = 0 if pickup else int(getattr(order, "shipping_cents", 0) or 0)
    discount = int(getattr(order, "discount_cents", 0) or 0)
    subtotal = int(getattr(order, "subtotal_cents", 0) or 0)
    total = int(getattr(order, "total_cents", subtotal + shipping - discount))
    delivery_type = "Retirada" if pickup else "Entrega"
    order_code = f"#{order.id[:8]}"
    items_text = format_status_items(items_payload)
    shipping_text = f"R$ {format_money(shipping)}"
    discount_text = f"R$ {format_money(discount)}"
    total_text = f"R$ {format_money(total)}"
    cfg = (
        db.query(models.OperationsConfig)
        .filter(models.OperationsConfig.tenant_id == order.tenant_id)
        .first()
    )
    template = cfg.whatsapp_status_message if cfg else None
    if template:
        values = {
            "customer_name": customer_name,
            "order_code": order_code,
            "status": status_text,
            "items": items_text,
            "shipping": shipping_text,
            "discount": discount_text,
            "total": total_text,
            "delivery_type": delivery_type,
            "address": address_text,
            "shipping_line": f"Frete: {shipping_text}" if shipping > 0 else "",
            "discount_line": f"Desconto: {discount_text}" if discount > 0 else "",
        }
        return render_template(template, values)
    return format_order_status_message(
        order_code=order_code,
        customer_name=customer_name,
        status_text=status_text,
        items=items_payload,
        shipping_cents=shipping,
        discount_cents=discount,
        total_cents=total,
        delivery_type=delivery_type,
        address_text=address_text,
    )


def _log_message(
    db: Session,
    *,
    tenant_id: str,
    order_id: str | None,
    to_phone: str,
    message: str,
    status: str,
    provider_message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    log = models.WhatsAppMessageLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        order_id=order_id,
        to_phone=to_phone,
        message=message,
        status=status,
        provider_message_id=provider_message_id,
        error_message=error_message,
    )
    db.add(log)
    db.commit()


def _messages_module_enabled(db: Session, tenant_id: str) -> bool:
    return (
        db.query(models.TenantModule)
        .filter(models.TenantModule.tenant_id == tenant_id, models.TenantModule.module == "messages")
        .first()
        is not None
    )


def _load_whatsapp_settings(db: Session, tenant_id: str) -> tuple[bool, str | None, str | None, str | None]:
    cfg = (
        db.query(models.OperationsConfig)
        .filter(models.OperationsConfig.tenant_id == tenant_id)
        .first()
    )
    if not _messages_module_enabled(db, tenant_id):
        return False, None, None, "messages module disabled"
    if not cfg:
        return False, None, None, "missing config"
    enabled = bool(cfg.whatsapp_enabled) if cfg.whatsapp_enabled is not None else False
    token = cfg.whatsapp_token
    phone_number_id = cfg.whatsapp_phone_number_id
    return enabled, token, phone_number_id, None


async def send_order_whatsapp(tenant_id: str, order_id: str) -> None:
    db = SessionLocal()
    try:
        order = (
            db.query(models.Order)
            .filter(models.Order.id == order_id, models.Order.tenant_id == tenant_id)
            .first()
        )
        if not order:
            return

        customer = (
            db.query(models.Customer)
            .filter(models.Customer.id == order.customer_id, models.Customer.tenant_id == tenant_id)
            .first()
        )
        if not customer:
            return

        payment = (
            db.query(models.Payment)
            .filter(models.Payment.order_id == order.id, models.Payment.tenant_id == tenant_id)
            .first()
        )
        payment_method = payment.method.value if payment else "-"

        address = None
        if order.address_id:
            address = (
                db.query(models.CustomerAddress)
                .filter(
                    models.CustomerAddress.id == order.address_id,
                    models.CustomerAddress.tenant_id == tenant_id,
                )
                .first()
            )

        items_rows = (
            db.query(models.OrderItem, models.Product)
            .join(models.Product, models.Product.id == models.OrderItem.product_id)
            .filter(
                models.OrderItem.order_id == order.id,
                models.OrderItem.tenant_id == tenant_id,
                models.Product.tenant_id == tenant_id,
            )
            .all()
        )
        items_payload = [
            {
                "name": product.name,
                "quantity": item.quantity,
                "unit_price_cents": item.unit_price_cents,
            }
            for (item, product) in items_rows
        ]

        pickup = not bool(order.address_id)
        address_text = _build_address_text(address, pickup)
        subtotal = int(getattr(order, "subtotal_cents", 0) or 0)
        shipping = 0 if pickup else int(getattr(order, "shipping_cents", 0) or 0)
        discount = int(getattr(order, "discount_cents", 0) or 0)
        total = int(getattr(order, "total_cents", subtotal + shipping - discount))

        message = format_order_message(
            order_id=order.id,
            customer_name=customer.name or "Customer",
            phone=customer.phone or "-",
            pickup=pickup,
            address_text=address_text,
            window_start=getattr(order, "delivery_window_start", None).isoformat()
            if getattr(order, "delivery_window_start", None)
            else None,
            window_end=getattr(order, "delivery_window_end", None).isoformat()
            if getattr(order, "delivery_window_end", None)
            else None,
            delivery_date=getattr(order, "delivery_date", None).isoformat()
            if getattr(order, "delivery_date", None)
            else None,
            items=items_payload,
            payment_method=payment_method,
            subtotal_cents=subtotal,
            shipping_cents=shipping,
            discount_cents=discount,
            total_cents=total,
        )
        await send_whatsapp_message(
            tenant_id=tenant_id,
            order_id=order.id,
            to_phone=customer.phone or "",
            text=message,
            db=db,
        )
    finally:
        db.close()


async def send_whatsapp_message(
    *,
    tenant_id: str,
    order_id: str | None,
    to_phone: str,
    text: str,
    db: Session,
) -> None:
    enabled, token, phone_number_id, disabled_reason = _load_whatsapp_settings(db, tenant_id)
    if not enabled:
        normalized_phone = normalize_phone(to_phone)
        _log_message(
            db,
            tenant_id=tenant_id,
            order_id=order_id,
            to_phone=normalized_phone or to_phone,
            message=text,
            status="blocked",
            error_message=disabled_reason or "disabled",
        )
        return
    normalized_phone = normalize_phone(to_phone)
    if not token or not phone_number_id:
        _log_message(
            db,
            tenant_id=tenant_id,
            order_id=order_id,
            to_phone=normalized_phone or to_phone,
            message=text,
            status="skipped",
            error_message="missing token/phone_number_id",
        )
        return
    if not normalized_phone:
        _log_message(
            db,
            tenant_id=tenant_id,
            order_id=order_id,
            to_phone=to_phone,
            message=text,
            status="skipped",
            error_message="missing destination phone",
        )
        return

    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": normalized_phone,
        "type": "text",
        "text": {"body": text},
    }
    timeouts = [10, 10, 10]
    backoffs = [0.5, 1.0]
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeouts[attempt]) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                data = response.json()
                message_id = None
                if isinstance(data, dict):
                    messages = data.get("messages") or []
                    if messages and isinstance(messages, list):
                        message_id = messages[0].get("id")
                _log_message(
                    db,
                    tenant_id=tenant_id,
                    order_id=order_id,
                    to_phone=normalized_phone,
                    message=text,
                    status="sent",
                    provider_message_id=message_id,
                )
                return
        except httpx.HTTPStatusError as exc:
            body = exc.response.text
            logger.warning(
                "WhatsApp send failed (attempt %s) status=%s body=%s",
                attempt + 1,
                exc.response.status_code,
                body,
            )
            if attempt == len(backoffs):
                _log_message(
                    db,
                    tenant_id=tenant_id,
                    order_id=order_id,
                    to_phone=normalized_phone,
                    message=text,
                    status="failed",
                    error_message=body,
                )
        except Exception as exc:
            logger.exception("Failed to send WhatsApp message (attempt %s)", attempt + 1)
            if attempt == len(backoffs):
                _log_message(
                    db,
                    tenant_id=tenant_id,
                    order_id=order_id,
                    to_phone=normalized_phone,
                    message=text,
                    status="failed",
                    error_message=str(exc),
                )
        if attempt < len(backoffs):
            await asyncio.sleep(backoffs[attempt])


async def send_order_status_whatsapp(
    *,
    tenant_id: str,
    order_id: str,
    status: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        order = (
            db.query(models.Order)
            .filter(models.Order.id == order_id, models.Order.tenant_id == tenant_id)
            .first()
        )
        if not order:
            return
        customer = (
            db.query(models.Customer)
            .filter(models.Customer.id == order.customer_id, models.Customer.tenant_id == tenant_id)
            .first()
        )
        if not customer:
            return
        message = build_order_status_message(db, order=order, status=status, customer=customer)
        normalized_phone = normalize_phone(customer.phone or "")
        if not normalized_phone:
            _log_message(
                db,
                tenant_id=tenant_id,
                order_id=order.id,
                to_phone=customer.phone or "",
                message=message,
                status="skipped",
                error_message="missing destination phone",
            )
            return
        if not _whatsapp_window_open(db, tenant_id=tenant_id, phone=normalized_phone):
            _log_message(
                db,
                tenant_id=tenant_id,
                order_id=order.id,
                to_phone=normalized_phone,
                message=message,
                status="skipped",
                error_message="outside window",
            )
            return
        await send_whatsapp_message(
            tenant_id=tenant_id,
            order_id=order.id,
            to_phone=customer.phone or "",
            text=message,
            db=db,
        )
    finally:
        db.close()
