import hashlib
import hmac
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.db import get_db, settings
from app.domain.billing.enums import SubscriptionStatus
from app.phone import normalize_phone
from app.services.subscriptions import assign_plan_to_tenant, sync_tenant_modules

router = APIRouter(prefix="/billing/webhook", tags=["billing-webhook"])


def _normalize_signature(signature: str | None) -> str | None:
    if not signature:
        return None
    if signature.startswith("sha256="):
        return signature.split("=", 1)[1]
    return signature


def _verify_signature(raw_body: bytes, signature: str | None) -> None:
    secrets = settings.BILLING_WEBHOOK_SECRETS_LIST
    if not secrets:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    normalized = _normalize_signature(signature)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
    for secret in secrets:
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, normalized):
            return
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _normalize_slug(value: object) -> str:
    cleaned = str(value or "").strip().lower()
    if not cleaned:
        raise HTTPException(status_code=400, detail="tenant_slug is required")
    return cleaned


def _normalize_document(value: object) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits or None


def _normalize_postal_code(value: object) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return None
    if len(digits) != 8:
        raise HTTPException(status_code=400, detail="billing_postal_code must have 8 digits")
    return digits


def _normalize_state(value: object) -> str | None:
    cleaned = _normalize_text(value)
    if cleaned is None:
        return None
    normalized = cleaned.upper()
    if len(normalized) != 2:
        raise HTTPException(status_code=400, detail="billing_state must have 2 chars")
    return normalized


def _parse_iso_datetime(value: object) -> datetime | None:
    cleaned = _normalize_text(value)
    if cleaned is None:
        return None
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="activated_at must be a valid ISO datetime")


def _normalize_person_type(value: object) -> models.CustomerPersonType:
    cleaned = str(value or "").strip().lower()
    if cleaned in ("individual", "cpf", "pf"):
        return models.CustomerPersonType.individual
    return models.CustomerPersonType.company


def _apply_intake_payload_to_tenant(tenant: models.Tenant, payload: dict, *, is_new: bool) -> None:
    if is_new or "name" in payload:
        tenant.name = _normalize_text(payload.get("name")) or _normalize_text(payload.get("trade_name")) or tenant.slug

    if "users_limit" in payload:
        try:
            users_limit = int(payload.get("users_limit"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="users_limit must be integer")
        if users_limit < 1:
            raise HTTPException(status_code=400, detail="users_limit must be >= 1")
        tenant.users_limit = users_limit
    elif is_new:
        tenant.users_limit = 5

    if "stores_limit" in payload:
        raw_stores_limit = payload.get("stores_limit")
        if raw_stores_limit is None or raw_stores_limit == "":
            tenant.stores_limit = None
        else:
            try:
                stores_limit = int(raw_stores_limit)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="stores_limit must be integer or null")
            if stores_limit < 1:
                raise HTTPException(status_code=400, detail="stores_limit must be >= 1")
            tenant.stores_limit = stores_limit

    if is_new:
        tenant.status = models.TenantStatus.active

    if "person_type" in payload:
        tenant.person_type = _normalize_person_type(payload.get("person_type"))
    elif is_new:
        tenant.person_type = models.CustomerPersonType.company

    if "document" in payload or "cnpj" in payload:
        tenant.document = _normalize_document(payload.get("document") or payload.get("cnpj"))

    if "legal_name" in payload:
        tenant.legal_name = _normalize_text(payload.get("legal_name"))
    if "trade_name" in payload:
        tenant.trade_name = _normalize_text(payload.get("trade_name"))
    if "state_registration" in payload:
        tenant.state_registration = _normalize_text(payload.get("state_registration"))
    if "municipal_registration" in payload:
        tenant.municipal_registration = _normalize_text(payload.get("municipal_registration"))
    if "contact_name" in payload:
        tenant.contact_name = _normalize_text(payload.get("contact_name"))
    if "contact_email" in payload:
        tenant.contact_email = _normalize_text(payload.get("contact_email"))
    if "contact_phone" in payload:
        tenant.contact_phone = normalize_phone(_normalize_text(payload.get("contact_phone"))) or None
    if "financial_contact_name" in payload:
        tenant.financial_contact_name = _normalize_text(payload.get("financial_contact_name"))
    if "financial_contact_email" in payload:
        tenant.financial_contact_email = _normalize_text(payload.get("financial_contact_email"))
    if "financial_contact_phone" in payload:
        tenant.financial_contact_phone = normalize_phone(_normalize_text(payload.get("financial_contact_phone"))) or None
    if "billing_postal_code" in payload:
        tenant.billing_postal_code = _normalize_postal_code(payload.get("billing_postal_code"))
    if "billing_street" in payload:
        tenant.billing_street = _normalize_text(payload.get("billing_street"))
    if "billing_number" in payload:
        tenant.billing_number = _normalize_text(payload.get("billing_number"))
    if "billing_district" in payload:
        tenant.billing_district = _normalize_text(payload.get("billing_district"))
    if "billing_city" in payload:
        tenant.billing_city = _normalize_text(payload.get("billing_city"))
    if "billing_state" in payload:
        tenant.billing_state = _normalize_state(payload.get("billing_state"))
    if "billing_complement" in payload:
        tenant.billing_complement = _normalize_text(payload.get("billing_complement"))

    if "onboarding_origin" in payload:
        tenant.onboarding_origin = _normalize_text(payload.get("onboarding_origin")) or "landing_page"
    elif is_new and not tenant.onboarding_origin:
        tenant.onboarding_origin = "landing_page"

    if "activation_mode" in payload:
        tenant.activation_mode = _normalize_text(payload.get("activation_mode")) or "automatic_webhook"
    elif is_new and not tenant.activation_mode:
        tenant.activation_mode = "automatic_webhook"

    if "payment_provider" in payload:
        tenant.payment_provider = _normalize_text(payload.get("payment_provider"))
    if "payment_reference" in payload:
        tenant.payment_reference = _normalize_text(payload.get("payment_reference"))
    if "activation_notes" in payload:
        tenant.activation_notes = _normalize_text(payload.get("activation_notes"))
    if "activated_at" in payload:
        tenant.activated_at = _parse_iso_datetime(payload.get("activated_at"))

    signup_payload = payload.get("signup_payload")
    if signup_payload is not None and not isinstance(signup_payload, dict):
        raise HTTPException(status_code=400, detail="signup_payload must be an object")
    tenant.signup_payload_json = json.dumps(signup_payload if isinstance(signup_payload, dict) else payload)


@router.post("/status")
async def update_subscription_status(
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    raw_body = await request.body()
    _verify_signature(raw_body, x_signature)
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    tenant_id = payload.get("tenant_id")
    status = payload.get("status")
    plan_id = payload.get("plan_id")
    if not tenant_id or not status:
        raise HTTPException(status_code=400, detail="Invalid payload")
    try:
        new_status = SubscriptionStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown status")

    subscription = (
        db.query(models.Subscription)
        .filter(models.Subscription.tenant_id == tenant_id)
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if plan_id:
        subscription.plan_id = plan_id
    subscription.status = new_status
    db.commit()

    # If status is not active/trialing, clear modules
    if new_status not in (SubscriptionStatus.active, SubscriptionStatus.trialing):
        sync_tenant_modules(db, tenant_id, [])
    return {"ok": True, "status": subscription.status.value}


@router.post("/intake")
async def intake_tenant_after_payment(
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    raw_body = await request.body()
    _verify_signature(raw_body, x_signature)
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")

    slug = _normalize_slug(payload.get("tenant_slug") or payload.get("slug"))
    plan_id = _normalize_text(payload.get("plan_id"))

    tenant = (
        db.query(models.Tenant)
        .filter(func.lower(models.Tenant.slug) == slug)
        .first()
    )
    created = False
    if tenant is None:
        tenant = models.Tenant(
            id=str(uuid.uuid4()),
            slug=slug,
            name=_normalize_text(payload.get("name")) or slug,
            status=models.TenantStatus.active,
            users_limit=5,
            stores_limit=None,
            person_type=models.CustomerPersonType.company,
            onboarding_origin="landing_page",
            activation_mode="automatic_webhook",
        )
        db.add(tenant)
        created = True

    _apply_intake_payload_to_tenant(tenant, payload, is_new=created)
    db.commit()
    db.refresh(tenant)

    if plan_id:
        assign_plan_to_tenant(db, tenant.id, plan_id)

    return {"ok": True, "tenant_id": tenant.id, "tenant_slug": tenant.slug, "created": created}
