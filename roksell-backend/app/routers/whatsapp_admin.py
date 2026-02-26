import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import require_roles
from app.db import get_db
from app.services.whatsapp import normalize_phone, send_whatsapp_message, WHATSAPP_WINDOW_HOURS
from app.services.webpush import get_web_push_public_key, web_push_enabled
from app.phone import phone_candidates
from app.tenancy import TenantContext, get_tenant_context

router = APIRouter(prefix="/admin/whatsapp", tags=["admin-whatsapp"])


def _get_or_create_config(db: Session, tenant_id: str) -> models.OperationsConfig:
    cfg = (
        db.query(models.OperationsConfig)
        .filter(models.OperationsConfig.tenant_id == tenant_id)
        .first()
    )
    if not cfg:
        cfg = models.OperationsConfig(tenant_id=tenant_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _unread_count_query(db: Session, tenant_id: str):
    return (
        db.query(func.count(models.WhatsAppInboundMessage.id))
        .outerjoin(
            models.WhatsAppConversation,
            and_(
                models.WhatsAppConversation.tenant_id == models.WhatsAppInboundMessage.tenant_id,
                models.WhatsAppConversation.phone == models.WhatsAppInboundMessage.from_phone,
            ),
        )
        .filter(models.WhatsAppInboundMessage.tenant_id == tenant_id)
        .filter(
            or_(
                models.WhatsAppConversation.last_read_at.is_(None),
                models.WhatsAppInboundMessage.received_at > models.WhatsAppConversation.last_read_at,
            )
        )
    )


@router.get("/logs", response_model=list[schemas.WhatsAppLogOut])
def list_whatsapp_logs(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
    order_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    page: int = Query(default=1, ge=1),
):
    query = db.query(models.WhatsAppMessageLog).filter(
        models.WhatsAppMessageLog.tenant_id == tenant.id
    )
    if order_id:
        query = query.filter(models.WhatsAppMessageLog.order_id == order_id)
    if status:
        query = query.filter(models.WhatsAppMessageLog.status == status)
    offset_val = (page - 1) * limit
    logs = (
        query.order_by(models.WhatsAppMessageLog.created_at.desc())
        .offset(offset_val)
        .limit(limit)
        .all()
    )
    return [
        schemas.WhatsAppLogOut(
            id=log.id,
            order_id=log.order_id,
            to_phone=log.to_phone,
            message=log.message,
            status=log.status,
            provider_message_id=log.provider_message_id,
            error_message=log.error_message,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/threads", response_model=list[schemas.WhatsAppThreadOut])
def list_threads(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
    limit: int = Query(default=200, ge=1, le=500),
):
    rows = (
        db.query(models.WhatsAppInboundMessage)
        .filter(models.WhatsAppInboundMessage.tenant_id == tenant.id)
        .order_by(models.WhatsAppInboundMessage.received_at.desc())
        .limit(limit)
        .all()
    )
    threads: dict[str, schemas.WhatsAppThreadOut] = {}
    for row in rows:
        if row.from_phone not in threads:
            threads[row.from_phone] = schemas.WhatsAppThreadOut(
                phone=row.from_phone,
                customer_name=None,
                last_message=row.message_text or row.message_type or "(midia)",
                last_received_at=row.received_at,
                total=1,
                unread_count=0,
            )
        else:
            threads[row.from_phone].total += 1

    if threads:
        phones = list(threads.keys())
        unread_rows = (
            db.query(
                models.WhatsAppInboundMessage.from_phone.label("from_phone"),
                func.count(models.WhatsAppInboundMessage.id).label("qty"),
            )
            .outerjoin(
                models.WhatsAppConversation,
                and_(
                    models.WhatsAppConversation.tenant_id == models.WhatsAppInboundMessage.tenant_id,
                    models.WhatsAppConversation.phone == models.WhatsAppInboundMessage.from_phone,
                ),
            )
            .filter(models.WhatsAppInboundMessage.tenant_id == tenant.id)
            .filter(models.WhatsAppInboundMessage.from_phone.in_(phones))
            .filter(
                or_(
                    models.WhatsAppConversation.last_read_at.is_(None),
                    models.WhatsAppInboundMessage.received_at > models.WhatsAppConversation.last_read_at,
                )
            )
            .group_by(models.WhatsAppInboundMessage.from_phone)
            .all()
        )
        unread_map = {str(row.from_phone): int(row.qty or 0) for row in unread_rows}
        customer_rows = (
            db.query(models.Customer.name, models.Customer.phone)
            .filter(models.Customer.tenant_id == tenant.id)
            .all()
        )
        customer_map = {normalize_phone(phone): name for name, phone in customer_rows if phone}
        conversation_rows = (
            db.query(models.WhatsAppConversation.phone, models.WhatsAppConversation.profile_name)
            .filter(models.WhatsAppConversation.tenant_id == tenant.id)
            .filter(models.WhatsAppConversation.phone.in_(list(threads.keys())))
            .all()
        )
        whatsapp_name_map = {
            normalize_phone(phone): profile_name
            for phone, profile_name in conversation_rows
            if phone and profile_name
        }
        for phone, thread in threads.items():
            normalized_phone = normalize_phone(phone)
            thread.unread_count = int(unread_map.get(phone, 0))
            customer_name = customer_map.get(normalized_phone)
            if customer_name:
                thread.customer_name = customer_name
                continue
            whatsapp_name = whatsapp_name_map.get(normalized_phone)
            if whatsapp_name:
                thread.customer_name = whatsapp_name

    sorted_threads = sorted(
        threads.values(),
        key=lambda item: item.last_received_at,
        reverse=True,
    )
    return sorted_threads


@router.get("/messages", response_model=list[schemas.WhatsAppInboundMessageOut])
def list_inbound_messages(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
    phone: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    page: int = Query(default=1, ge=1),
):
    query = db.query(models.WhatsAppInboundMessage).filter(
        models.WhatsAppInboundMessage.tenant_id == tenant.id
    )
    if phone:
        candidates = phone_candidates(phone)
        if candidates:
            query = query.filter(models.WhatsAppInboundMessage.from_phone.in_(candidates))
        else:
            return []
    offset_val = (page - 1) * limit
    rows = (
        query.order_by(models.WhatsAppInboundMessage.received_at.desc())
        .offset(offset_val)
        .limit(limit)
        .all()
    )
    return [
        schemas.WhatsAppInboundMessageOut(
            id=row.id,
            from_phone=row.from_phone,
            provider_message_id=row.provider_message_id,
            message_type=row.message_type,
            message_text=row.message_text,
            media_url=getattr(row, "media_url", None),
            media_mime=getattr(row, "media_mime", None),
            received_at=row.received_at,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/conversation", response_model=list[schemas.WhatsAppConversationMessageOut])
def list_conversation_messages(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
    phone: str = Query(...),
    limit: int = Query(default=200, ge=1, le=500),
    page: int = Query(default=1, ge=1),
):
    candidates = phone_candidates(phone)
    if not candidates:
        return []

    inbound_rows = (
        db.query(models.WhatsAppInboundMessage)
        .filter(models.WhatsAppInboundMessage.tenant_id == tenant.id)
        .filter(models.WhatsAppInboundMessage.from_phone.in_(candidates))
        .order_by(models.WhatsAppInboundMessage.received_at.desc())
        .limit(limit)
        .all()
    )
    outbound_rows = (
        db.query(models.WhatsAppMessageLog)
        .filter(models.WhatsAppMessageLog.tenant_id == tenant.id)
        .filter(models.WhatsAppMessageLog.to_phone.in_(candidates))
        .order_by(models.WhatsAppMessageLog.created_at.desc())
        .limit(limit)
        .all()
    )

    combined: list[dict] = []
    for row in inbound_rows:
        combined.append(
            {
                "id": row.id,
                "direction": "inbound",
                "phone": row.from_phone,
                "message_type": row.message_type,
                "message_text": row.message_text,
                "media_url": getattr(row, "media_url", None),
                "media_mime": getattr(row, "media_mime", None),
                "status": None,
                "provider_message_id": row.provider_message_id,
                "created_at": row.received_at or row.created_at,
            }
        )
    for row in outbound_rows:
        combined.append(
            {
                "id": row.id,
                "direction": "outbound",
                "phone": row.to_phone,
                "message_type": None,
                "message_text": row.message,
                "media_url": None,
                "media_mime": None,
                "status": row.status,
                "provider_message_id": row.provider_message_id,
                "created_at": row.created_at,
            }
        )

    combined.sort(key=lambda item: item["created_at"], reverse=True)
    offset_val = (page - 1) * limit
    page_items = combined[offset_val : offset_val + limit]
    page_items.reverse()
    return [schemas.WhatsAppConversationMessageOut(**item) for item in page_items]


@router.get("/unread", response_model=schemas.WhatsAppUnreadOut)
def get_unread_count(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
):
    count = _unread_count_query(db, tenant.id).scalar() or 0
    return schemas.WhatsAppUnreadOut(count=int(count))


@router.post("/read", response_model=schemas.WhatsAppUnreadOut)
def mark_messages_read(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    phone: str | None = Query(default=None),
    _: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
):
    cfg = _get_or_create_config(db, tenant.id)
    now = datetime.now(timezone.utc)
    if phone:
        candidates = phone_candidates(phone)
        if candidates:
            contacts = (
                db.query(models.WhatsAppConversation)
                .filter(models.WhatsAppConversation.tenant_id == tenant.id)
                .filter(models.WhatsAppConversation.phone.in_(candidates))
                .all()
            )
            for contact in contacts:
                contact.last_read_at = now
            if not contacts:
                normalized_phone = normalize_phone(phone)
                if normalized_phone:
                    db.add(
                        models.WhatsAppConversation(
                            tenant_id=tenant.id,
                            phone=normalized_phone,
                            last_inbound_at=now,
                            last_read_at=now,
                        )
                    )
    else:
        (
            db.query(models.WhatsAppConversation)
            .filter(models.WhatsAppConversation.tenant_id == tenant.id)
            .update({models.WhatsAppConversation.last_read_at: now}, synchronize_session=False)
        )
        cfg.whatsapp_last_read_at = now
    db.commit()
    count = _unread_count_query(db, tenant.id).scalar() or 0
    return schemas.WhatsAppUnreadOut(count=int(count))


@router.post("/send", response_model=schemas.WhatsAppSendOut)
async def send_manual_message(
    payload: schemas.WhatsAppSendIn,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
):
    candidates = phone_candidates(payload.phone)
    if not candidates:
        raise HTTPException(status_code=400, detail="Invalid phone")
    contact = (
        db.query(models.WhatsAppConversation)
        .filter(models.WhatsAppConversation.tenant_id == tenant.id)
        .filter(models.WhatsAppConversation.phone.in_(candidates))
        .order_by(models.WhatsAppConversation.last_inbound_at.desc())
        .first()
    )
    if not contact:
        raise HTTPException(status_code=400, detail="outside window")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=WHATSAPP_WINDOW_HOURS)
    if contact.last_inbound_at < cutoff:
        raise HTTPException(status_code=400, detail="outside window")
    normalized = normalize_phone(payload.phone)
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid phone")
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text required")
    await send_whatsapp_message(
        tenant_id=tenant.id,
        order_id=None,
        to_phone=normalized,
        text=text,
        db=db,
    )
    return schemas.WhatsAppSendOut(ok=True)


@router.get("/push/public-key", response_model=schemas.WhatsAppPushPublicKeyOut)
def get_push_public_key(
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
):
    _ = tenant
    return schemas.WhatsAppPushPublicKeyOut(
        enabled=web_push_enabled(),
        public_key=get_web_push_public_key(),
    )


@router.post("/push/subscribe", response_model=schemas.WhatsAppSendOut)
def subscribe_push_notifications(
    payload: schemas.WhatsAppPushSubscriptionIn,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
):
    endpoint = (payload.endpoint or "").strip()
    p256dh = (payload.keys.p256dh or "").strip()
    auth = (payload.keys.auth or "").strip()
    if not endpoint or not p256dh or not auth:
        raise HTTPException(status_code=400, detail="Invalid subscription payload")
    expiration_time = None
    raw_expiration = payload.expirationTime
    if isinstance(raw_expiration, datetime):
        expiration_time = raw_expiration
    elif isinstance(raw_expiration, (int, float)) and raw_expiration > 0:
        timestamp_seconds = raw_expiration / 1000 if raw_expiration > 10_000_000_000 else raw_expiration
        try:
            expiration_time = datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            expiration_time = None

    existing = (
        db.query(models.WhatsAppPushSubscription)
        .filter(
            models.WhatsAppPushSubscription.tenant_id == tenant.id,
            models.WhatsAppPushSubscription.endpoint == endpoint,
        )
        .first()
    )
    if existing:
        existing.user_id = user.id
        existing.p256dh = p256dh
        existing.auth = auth
        existing.expiration_time = expiration_time
        existing.user_agent = payload.user_agent
        existing.updated_at = datetime.now(timezone.utc)
    else:
        now_utc = datetime.now(timezone.utc)
        db.add(
            models.WhatsAppPushSubscription(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                user_id=user.id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                expiration_time=expiration_time,
                user_agent=payload.user_agent,
                created_at=now_utc,
                updated_at=now_utc,
            )
        )
    db.commit()
    return schemas.WhatsAppSendOut(ok=True)


@router.post("/push/unsubscribe", response_model=schemas.WhatsAppSendOut)
def unsubscribe_push_notifications(
    payload: schemas.WhatsAppPushSubscriptionRemoveIn,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
):
    endpoint = (payload.endpoint or "").strip()
    if not endpoint:
        raise HTTPException(status_code=400, detail="Invalid endpoint")
    (
        db.query(models.WhatsAppPushSubscription)
        .filter(
            models.WhatsAppPushSubscription.tenant_id == tenant.id,
            models.WhatsAppPushSubscription.endpoint == endpoint,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return schemas.WhatsAppSendOut(ok=True)
