"""
Router de checkout: orquestra request/response e notificações em background.
Toda a lógica de negócio e persistência está em app.services.checkout.
"""
import logging
import os

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
