from __future__ import annotations

import asyncio
import json
import logging
import os
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger(__name__)


def _load_web_push_config() -> tuple[str | None, str | None, str]:
    public_key = (os.getenv("WEB_PUSH_PUBLIC_KEY") or "").strip() or None
    private_key = (os.getenv("WEB_PUSH_PRIVATE_KEY") or "").strip() or None
    subject = (os.getenv("WEB_PUSH_SUBJECT") or "mailto:admin@localhost").strip() or "mailto:admin@localhost"
    return public_key, private_key, subject


def get_web_push_public_key() -> str | None:
    public_key, _, _ = _load_web_push_config()
    return public_key


def web_push_enabled() -> bool:
    public_key, private_key, _ = _load_web_push_config()
    return bool(public_key and private_key)


def _build_push_payload(notification: dict) -> str:
    phone = str(notification.get("phone") or "")
    customer_name = str(notification.get("customer_name") or "").strip()
    message_preview = str(notification.get("message_preview") or "").strip()
    display_name = customer_name or phone or "Cliente"
    if message_preview:
        body = f"{display_name}: {message_preview}"
    else:
        body = f"Nova mensagem de {display_name}"
    url_phone = quote_plus(phone) if phone else ""
    url = f"/portal/mensagens?phone={url_phone}" if url_phone else "/portal/mensagens"
    payload = {
        "title": "Nova mensagem no WhatsApp",
        "body": body,
        "url": url,
        "phone": phone,
        "customer_name": customer_name or None,
        "tag": f"whatsapp-{phone}" if phone else "whatsapp",
    }
    return json.dumps(payload, ensure_ascii=True)


def _format_brl(cents: int | float | None) -> str:
    try:
        value = float(cents or 0) / 100
    except Exception:
        value = 0.0
    return f"R$ {value:.2f}".replace(".", ",")


def _build_order_payload(notification: dict) -> str:
    order_id = str(notification.get("order_id") or "")
    customer_name = str(notification.get("customer_name") or "").strip()
    total_cents = notification.get("total_cents")
    display_name = customer_name or "Cliente"
    short_id = order_id.split("-")[0][:8] if order_id else ""
    order_label = f"#{short_id}" if short_id else "novo pedido"
    total_label = _format_brl(total_cents)
    body = f"{display_name} · Pedido {order_label} · {total_label}"
    url = "/portal/pedidos"
    payload = {
        "title": "Novo pedido recebido",
        "body": body,
        "url": url,
        "order_id": order_id or None,
        "customer_name": customer_name or None,
        "tag": f"order-{order_id}" if order_id else "order",
    }
    return json.dumps(payload, ensure_ascii=True)


def _get_status_code(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    return None


async def send_whatsapp_push_notifications(db: Session, notifications: list[dict]) -> None:
    if not notifications:
        return
    public_key, private_key, subject = _load_web_push_config()
    if not public_key or not private_key:
        return

    try:
        from pywebpush import WebPushException, webpush
    except Exception:
        logger.warning("pywebpush is not installed; skipping push notification dispatch")
        return

    by_tenant: dict[str, list[dict]] = {}
    for item in notifications:
        tenant_id = str(item.get("tenant_id") or "").strip()
        if not tenant_id:
            continue
        by_tenant.setdefault(tenant_id, []).append(item)

    stale_ids: set[str] = set()

    for tenant_id, tenant_notifications in by_tenant.items():
        subscriptions = (
            db.query(models.WhatsAppPushSubscription)
            .filter(models.WhatsAppPushSubscription.tenant_id == tenant_id)
            .all()
        )
        if not subscriptions:
            continue
        for notification in tenant_notifications:
            payload = _build_push_payload(notification)
            for subscription in subscriptions:
                sub_info = {
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth,
                    },
                }
                try:
                    await asyncio.to_thread(
                        webpush,
                        subscription_info=sub_info,
                        data=payload,
                        vapid_private_key=private_key,
                        vapid_claims={"sub": subject},
                        ttl=30,
                    )
                except WebPushException as exc:
                    status_code = _get_status_code(exc)
                    if status_code in {404, 410}:
                        stale_ids.add(subscription.id)
                    else:
                        logger.warning(
                            "Web Push send failed tenant=%s subscription=%s status=%s",
                            tenant_id,
                            subscription.id,
                            status_code,
                        )
                except Exception:
                    logger.exception(
                        "Web Push send failed tenant=%s subscription=%s",
                        tenant_id,
                        subscription.id,
                    )

    if stale_ids:
        (
            db.query(models.WhatsAppPushSubscription)
            .filter(models.WhatsAppPushSubscription.id.in_(list(stale_ids)))
            .delete(synchronize_session=False)
        )
        db.commit()


def send_order_push_notifications(notifications: list[dict]) -> None:
    if not notifications:
        return
    public_key, private_key, subject = _load_web_push_config()
    if not public_key or not private_key:
        return

    try:
        from pywebpush import WebPushException, webpush
    except Exception:
        logger.warning("pywebpush is not installed; skipping order push notifications")
        return

    from app.db import SessionLocal

    db = SessionLocal()
    try:
        by_tenant: dict[str, list[dict]] = {}
        for item in notifications:
            tenant_id = str(item.get("tenant_id") or "").strip()
            if not tenant_id:
                continue
            by_tenant.setdefault(tenant_id, []).append(item)

        stale_ids: set[str] = set()

        for tenant_id, tenant_notifications in by_tenant.items():
            subscriptions = (
                db.query(models.WhatsAppPushSubscription)
                .filter(models.WhatsAppPushSubscription.tenant_id == tenant_id)
                .all()
            )
            if not subscriptions:
                continue
            for notification in tenant_notifications:
                payload = _build_order_payload(notification)
                for subscription in subscriptions:
                    sub_info = {
                        "endpoint": subscription.endpoint,
                        "keys": {
                            "p256dh": subscription.p256dh,
                            "auth": subscription.auth,
                        },
                    }
                    try:
                        webpush(
                            subscription_info=sub_info,
                            data=payload,
                            vapid_private_key=private_key,
                            vapid_claims={"sub": subject},
                            ttl=30,
                        )
                    except WebPushException as exc:
                        status_code = _get_status_code(exc)
                        if status_code in {404, 410}:
                            stale_ids.add(subscription.id)
                        else:
                            logger.warning(
                                "Order push send failed tenant=%s subscription=%s status=%s",
                                tenant_id,
                                subscription.id,
                                status_code,
                            )
                    except Exception:
                        logger.exception(
                            "Order push send failed tenant=%s subscription=%s",
                            tenant_id,
                            subscription.id,
                        )

        if stale_ids:
            (
                db.query(models.WhatsAppPushSubscription)
                .filter(models.WhatsAppPushSubscription.id.in_(list(stale_ids)))
                .delete(synchronize_session=False)
            )
            db.commit()
    finally:
        db.close()
