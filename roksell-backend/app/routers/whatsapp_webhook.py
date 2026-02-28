from __future__ import annotations

import hmac
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app import models
from app.db import get_db, settings
from app.services.whatsapp import build_order_status_message, send_whatsapp_message
from app.services.whatsapp import normalize_phone
from app.services.webpush import send_whatsapp_push_notifications
from app.storage import build_media_key, storage_save
from app.tenancy import resolve_tenant

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp-webhook"])
logger = logging.getLogger(__name__)

ORDER_ID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

MEDIA_TYPES = {"image", "video", "audio", "document", "sticker"}
MEDIA_LABELS = {
    "image": "Imagem recebida",
    "video": "Video recebido",
    "audio": "Audio recebido",
    "document": "Documento recebido",
    "sticker": "Sticker recebido",
}
MEDIA_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "application/pdf": "pdf",
}


def _get_whatsapp_token(db: Session, tenant_id: str) -> str | None:
    cfg = (
        db.query(models.OperationsConfig)
        .filter(models.OperationsConfig.tenant_id == tenant_id)
        .first()
    )
    if not cfg:
        return os.getenv("WHATSAPP_TOKEN")
    if cfg.whatsapp_enabled is False:
        return None
    return cfg.whatsapp_token or os.getenv("WHATSAPP_TOKEN")


def _extension_for_mime(mime: str | None) -> str:
    if not mime:
        return "bin"
    return MEDIA_EXTENSIONS.get(mime, "bin")


async def _fetch_media_payload(token: str, media_id: str) -> tuple[bytes, str | None] | None:
    if not token or not media_id:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20) as client:
        meta_resp = await client.get(f"https://graph.facebook.com/v18.0/{media_id}", headers=headers)
        meta_resp.raise_for_status()
        meta = meta_resp.json()
        url = meta.get("url")
        if not url:
            return None
        mime = meta.get("mime_type")
        media_resp = await client.get(url, headers=headers)
        media_resp.raise_for_status()
        if not mime:
            mime = media_resp.headers.get("Content-Type")
        return media_resp.content, mime


def _verify_webhook(
    *,
    hub_mode: str | None,
    hub_verify_token: str | None,
    hub_challenge: str | None,
) -> str:
    expected = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
    if not expected:
        raise HTTPException(status_code=500, detail="Missing webhook verify token")
    if hub_mode != "subscribe" or hub_verify_token != expected:
        raise HTTPException(status_code=403, detail="Invalid webhook token")
    return hub_challenge or ""


def _verify_webhook_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    """Verifica X-Hub-Signature-256 (HMAC-SHA256 com App Secret da Meta)."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_hex = signature_header[7:].strip().lower()
    if len(expected_hex) != 64 or not all(c in "0123456789abcdef" for c in expected_hex):
        return False
    computed = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest().lower()
    return hmac.compare_digest(computed, expected_hex)


@router.get("", response_class=PlainTextResponse)
def verify_webhook_root(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    return _verify_webhook(
        hub_mode=hub_mode,
        hub_verify_token=hub_verify_token,
        hub_challenge=hub_challenge,
    )


@router.get("/{tenant_slug}", response_class=PlainTextResponse)
def verify_webhook(
    tenant_slug: str,
    db: Session = Depends(get_db),
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _verify_webhook(
        hub_mode=hub_mode,
        hub_verify_token=hub_verify_token,
        hub_challenge=hub_challenge,
    )


def _resolve_tenant_by_phone_number_id(db: Session, phone_number_id: str | None):
    if not phone_number_id:
        return None
    return (
        db.query(models.Tenant)
        .join(models.OperationsConfig, models.OperationsConfig.tenant_id == models.Tenant.id)
        .filter(models.OperationsConfig.whatsapp_phone_number_id == phone_number_id)
        .first()
    )


async def _process_payload(
    *,
    db: Session,
    tenant: models.Tenant | None,
    payload: dict,
):
    entries = payload.get("entry") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return {"ok": True}
    now = datetime.now(timezone.utc)
    phones_by_tenant: dict[str, set[str]] = {}
    last_inbound_by_tenant_phone: dict[str, dict[str, datetime]] = {}
    profile_name_by_tenant_phone: dict[str, dict[str, str]] = {}
    notifications: list[dict] = []
    inbound_messages: list[models.WhatsAppInboundMessage] = []
    for entry in entries:
        changes = entry.get("changes") if isinstance(entry, dict) else None
        if not isinstance(changes, list):
            continue
        for change in changes:
            value = change.get("value") if isinstance(change, dict) else None
            if not isinstance(value, dict):
                continue
            phone_number_id = None
            metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else None
            if metadata:
                phone_number_id = metadata.get("phone_number_id")
            resolved_tenant = tenant or _resolve_tenant_by_phone_number_id(db, phone_number_id)
            if resolved_tenant is None:
                continue
            contacts_value = value.get("contacts")
            contacts_by_phone: dict[str, str] = {}
            if isinstance(contacts_value, list):
                for contact_item in contacts_value:
                    if not isinstance(contact_item, dict):
                        continue
                    profile = contact_item.get("profile") if isinstance(contact_item.get("profile"), dict) else None
                    profile_name = (profile.get("name") if profile else None) or ""
                    profile_name = str(profile_name).strip()
                    if not profile_name:
                        continue
                    wa_id = str(contact_item.get("wa_id") or "").strip()
                    if wa_id:
                        contacts_by_phone[wa_id] = profile_name
                        normalized_wa = normalize_phone(wa_id)
                        if normalized_wa:
                            contacts_by_phone[normalized_wa] = profile_name
            messages = value.get("messages")
            if not isinstance(messages, list):
                continue
            for message in messages:
                if not isinstance(message, dict):
                    continue
                from_phone = message.get("from")
                normalized = normalize_phone(from_phone or "")
                if not normalized:
                    continue
                phones_by_tenant.setdefault(resolved_tenant.id, set()).add(normalized)
                profile_name = contacts_by_phone.get(normalized) or contacts_by_phone.get(from_phone or "")
                if profile_name:
                    profile_name_by_tenant_phone.setdefault(resolved_tenant.id, {})
                    profile_name_by_tenant_phone[resolved_tenant.id][normalized] = profile_name
                timestamp_raw = message.get("timestamp")
                received_at = now
                if timestamp_raw is not None:
                    try:
                        received_at = datetime.fromtimestamp(int(timestamp_raw), tz=timezone.utc)
                    except (TypeError, ValueError):
                        received_at = now
                last_inbound_by_tenant_phone.setdefault(resolved_tenant.id, {})
                last_inbound_by_tenant_phone[resolved_tenant.id][normalized] = max(
                    last_inbound_by_tenant_phone[resolved_tenant.id].get(normalized, received_at),
                    received_at,
                )
                provider_message_id = message.get("id")
                if provider_message_id:
                    existing = (
                        db.query(models.WhatsAppInboundMessage.id)
                        .filter(
                            models.WhatsAppInboundMessage.tenant_id == resolved_tenant.id,
                            models.WhatsAppInboundMessage.provider_message_id == provider_message_id,
                        )
                        .first()
                    )
                    if existing:
                        continue
                message_type = message.get("type")
                message_text = None
                media_url = None
                media_mime = None
                if message_type == "text":
                    text = message.get("text") if isinstance(message.get("text"), dict) else None
                    if text:
                        message_text = text.get("body")
                        match = ORDER_ID_PATTERN.search(message_text or "")
                        if match:
                            order_id = match.group(0)
                            order = (
                                db.query(models.Order)
                                .filter(models.Order.tenant_id == resolved_tenant.id, models.Order.id == order_id)
                                .first()
                            )
                            if order:
                                status_value = getattr(order, "status", "updated")
                                status_text = (
                                    status_value.value if hasattr(status_value, "value") else str(status_value)
                                )
                                reply = build_order_status_message(db, order=order, status=status_text)
                                await send_whatsapp_message(
                                    tenant_id=resolved_tenant.id,
                                    order_id=order.id,
                                    to_phone=normalized,
                                    text=reply,
                                    db=db,
                                )
                elif message_type in MEDIA_TYPES:
                    media_payload = message.get(message_type) if isinstance(message.get(message_type), dict) else None
                    if media_payload:
                        caption = media_payload.get("caption")
                        if caption:
                            message_text = str(caption)
                        media_id = media_payload.get("id")
                        media_mime = media_payload.get("mime_type") or None
                        token = _get_whatsapp_token(db, resolved_tenant.id)
                        if token and media_id:
                            try:
                                fetched = await _fetch_media_payload(token, str(media_id))
                            except Exception:
                                logger.exception("Failed to fetch WhatsApp media tenant=%s id=%s", resolved_tenant.id, media_id)
                                fetched = None
                            if fetched:
                                contents, fetched_mime = fetched
                                if fetched_mime:
                                    media_mime = fetched_mime
                                ext = _extension_for_mime(media_mime)
                                key = build_media_key(
                                    "tenants",
                                    resolved_tenant.slug,
                                    "whatsapp",
                                    normalized,
                                    f"{media_id}.{ext}",
                                )
                                try:
                                    media_url = storage_save(key, contents, media_mime)
                                except Exception:
                                    logger.exception("Failed to store WhatsApp media tenant=%s id=%s", resolved_tenant.id, media_id)
                                    media_url = None
                        else:
                            logger.info(
                                "WhatsApp media skipped tenant=%s has_token=%s has_media_id=%s",
                                resolved_tenant.id,
                                bool(token),
                                bool(media_id),
                            )
                message_preview = (message_text or "").strip()
                if not message_preview:
                    message_preview = MEDIA_LABELS.get(str(message_type or "").strip().lower(), "")
                if not message_preview:
                    message_preview = str(message_type or "").strip() or "Nova mensagem"
                customer_name = (
                    profile_name_by_tenant_phone.get(resolved_tenant.id, {}).get(normalized)
                    or ""
                )
                notifications.append(
                    {
                        "tenant_id": resolved_tenant.id,
                        "phone": normalized,
                        "customer_name": customer_name,
                        "message_preview": message_preview,
                    }
                )
                inbound_messages.append(
                    models.WhatsAppInboundMessage(
                        id=str(uuid.uuid4()),
                        tenant_id=resolved_tenant.id,
                        from_phone=normalized,
                        provider_message_id=provider_message_id,
                        message_type=message_type,
                        message_text=message_text,
                        media_url=media_url,
                        media_mime=media_mime,
                        payload_json=json.dumps(message, ensure_ascii=True),
                        received_at=received_at,
                    )
                )
    if not phones_by_tenant:
        return {"ok": True}
    for tenant_id, phones in phones_by_tenant.items():
        for phone in phones:
            contact = (
                db.query(models.WhatsAppConversation)
                .filter(
                    models.WhatsAppConversation.tenant_id == tenant_id,
                    models.WhatsAppConversation.phone == phone,
                )
                .first()
            )
            inbound_at = last_inbound_by_tenant_phone.get(tenant_id, {}).get(phone, now)
            if contact:
                contact.last_inbound_at = max(contact.last_inbound_at, inbound_at)
                profile_name = profile_name_by_tenant_phone.get(tenant_id, {}).get(phone)
                if profile_name:
                    contact.profile_name = profile_name
            else:
                db.add(
                    models.WhatsAppConversation(
                        tenant_id=tenant_id,
                        phone=phone,
                        profile_name=profile_name_by_tenant_phone.get(tenant_id, {}).get(phone),
                        last_inbound_at=inbound_at,
                    )
                )
    if inbound_messages:
        db.add_all(inbound_messages)
    db.commit()
    if notifications:
        await send_whatsapp_push_notifications(db, notifications)
    return {"ok": True}


@router.post("")
async def receive_webhook_root(
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    if not settings.whatsapp_app_secret:
        raise HTTPException(
            status_code=503,
            detail="Webhook signature verification not configured (set WHATSAPP_APP_SECRET)",
        )
    signature = request.headers.get("X-Hub-Signature-256")
    if not _verify_webhook_signature(raw_body, signature, settings.whatsapp_app_secret):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    return await _process_payload(db=db, tenant=None, payload=payload)


@router.post("/{tenant_slug}")
async def receive_webhook(
    tenant_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    raw_body = await request.body()
    if not settings.whatsapp_app_secret:
        raise HTTPException(
            status_code=503,
            detail="Webhook signature verification not configured (set WHATSAPP_APP_SECRET)",
        )
    signature = request.headers.get("X-Hub-Signature-256")
    if not _verify_webhook_signature(raw_body, signature, settings.whatsapp_app_secret):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    return await _process_payload(db=db, tenant=tenant, payload=payload)
