import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterable
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, text
from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.auth.dependencies import get_current_user
from app.db import get_db
from app.phone import normalize_phone
from app.security import hash_password
from app.services.subscriptions import assign_plan_to_tenant, sync_tenant_modules
from app.services.user_sessions import normalize_max_active_sessions, trim_user_sessions_to_limit
from app.tenancy import TenantContext, get_tenant_context, resolve_tenant

router = APIRouter(prefix="/admin/central", tags=["admin-central"])

SUPER_ADMIN_TENANT_SLUG = os.getenv("SUPER_ADMIN_TENANT_SLUG", "rokin").strip().lower()
PHONE_NUMBER_ID_RE = re.compile(r"^\d{6,20}$")
PLAN_IGNORED_MODULE_KEYS = {"config"}
ONBOARDING_FORCE_TEST_MODE = "force_first_access_test"


def require_super_admin(
    user: models.User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
) -> models.User:
    if tenant.slug != SUPER_ADMIN_TENANT_SLUG:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    if user.role != models.UserRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return user


class TenantCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    status: str = Field(default="active")
    users_limit: int = Field(default=5, ge=1)
    stores_limit: int | None = Field(default=None, ge=1)
    cnpj: str | None = None
    contact_email: EmailStr | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    legal_name: str | None = None
    trade_name: str | None = None
    state_registration: str | None = None
    municipal_registration: str | None = None
    financial_contact_name: str | None = None
    financial_contact_email: EmailStr | None = None
    financial_contact_phone: str | None = None
    billing_postal_code: str | None = None
    billing_street: str | None = None
    billing_number: str | None = None
    billing_district: str | None = None
    billing_city: str | None = None
    billing_state: str | None = None
    billing_complement: str | None = None
    onboarding_origin: str | None = None
    activation_mode: str | None = None
    payment_provider: str | None = None
    payment_reference: str | None = None
    activation_notes: str | None = None
    signup_payload: dict | None = None
    activated_at: datetime | None = None
    person_type: str | None = None
    document: str | None = None
    payment_link_enabled: bool | None = None
    payment_link_config: dict | None = None
    plan: str | None = None


class TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    users_limit: int
    stores_limit: int | None = None
    legal_name: str | None = None
    trade_name: str | None = None
    state_registration: str | None = None
    municipal_registration: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    financial_contact_name: str | None = None
    financial_contact_email: str | None = None
    financial_contact_phone: str | None = None
    billing_postal_code: str | None = None
    billing_street: str | None = None
    billing_number: str | None = None
    billing_district: str | None = None
    billing_city: str | None = None
    billing_state: str | None = None
    billing_complement: str | None = None
    onboarding_origin: str = "admin_manual"
    activation_mode: str = "manual"
    payment_provider: str | None = None
    payment_reference: str | None = None
    activation_notes: str | None = None
    signup_payload: dict | None = None
    activated_at: datetime | None = None
    person_type: str | None = None
    document: str | None = None
    payment_link_enabled: bool = False
    payment_link_config: dict | None = None


class TenantListOut(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    users_limit: int
    stores_limit: int | None = None
    legal_name: str | None = None
    trade_name: str | None = None
    state_registration: str | None = None
    municipal_registration: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    financial_contact_name: str | None = None
    financial_contact_email: str | None = None
    financial_contact_phone: str | None = None
    billing_postal_code: str | None = None
    billing_street: str | None = None
    billing_number: str | None = None
    billing_district: str | None = None
    billing_city: str | None = None
    billing_state: str | None = None
    billing_complement: str | None = None
    onboarding_origin: str = "admin_manual"
    activation_mode: str = "manual"
    payment_provider: str | None = None
    payment_reference: str | None = None
    activation_notes: str | None = None
    signup_payload: dict | None = None
    activated_at: datetime | None = None
    users_count: int
    stores_count: int
    created_at: str
    person_type: str | None = None
    document: str | None = None
    payment_link_enabled: bool = False
    payment_link_config: dict | None = None


class TenantUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None
    users_limit: int | None = Field(default=None, ge=1)
    stores_limit: int | None = Field(default=None, ge=1)
    legal_name: str | None = None
    trade_name: str | None = None
    state_registration: str | None = None
    municipal_registration: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    financial_contact_name: str | None = None
    financial_contact_email: EmailStr | None = None
    financial_contact_phone: str | None = None
    billing_postal_code: str | None = None
    billing_street: str | None = None
    billing_number: str | None = None
    billing_district: str | None = None
    billing_city: str | None = None
    billing_state: str | None = None
    billing_complement: str | None = None
    onboarding_origin: str | None = None
    activation_mode: str | None = None
    payment_provider: str | None = None
    payment_reference: str | None = None
    activation_notes: str | None = None
    signup_payload: dict | None = None
    activated_at: datetime | None = None
    person_type: str | None = None
    document: str | None = None
    payment_link_enabled: bool | None = None
    payment_link_config: dict | None = None


class UserCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default=models.UserRole.owner.value)
    max_active_sessions: int = Field(default=3, ge=1, le=20)
    tenant_slug: str
    default_store_id: str | None = None


class LimitsPayload(BaseModel):
    users_limit: int = Field(ge=1)
    stores_limit: int | None = None


class ModulesPayload(BaseModel):
    modules: list[str]


class MessagingConfigPayload(BaseModel):
    whatsapp_enabled: bool | None = None
    whatsapp_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    telegram_enabled: bool | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


class PlanCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True
    price_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    interval: str | None = None
    module_keys: list[str] = Field(default_factory=list)


class PlanUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    price_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    interval: str | None = None
    module_keys: list[str] | None = None


class PlanOutPayload(BaseModel):
    id: str
    name: str
    description: str | None = None
    is_active: bool
    price_cents: int
    currency: str
    interval: str
    modules: list[str]


class TenantPlanPayload(BaseModel):
    plan_id: str


class TenantPlanOut(BaseModel):
    plan_id: str | None = None
    plan_name: str | None = None
    status: str | None = None
    modules: list[str] = Field(default_factory=list)


class CentralDashboardOut(BaseModel):
    active_tenants_count: int
    active_users_now_count: int
    active_stores_count: int
    orders_today_count: int
    orders_month_count: int


def _normalized_slug(value: str) -> str:
    return value.strip().lower()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_person_type(value: str | None) -> models.CustomerPersonType | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned in ("pf", "cpf", "pessoa_fisica", "pessoa-fisica", "fisica"):
        return models.CustomerPersonType.individual
    if cleaned in ("pj", "cnpj", "pessoa_juridica", "pessoa-juridica", "juridica", "empresa"):
        return models.CustomerPersonType.company
    try:
        return models.CustomerPersonType(cleaned)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid person_type")


def _normalize_document(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


def _validate_document(person_type: models.CustomerPersonType, document: str) -> None:
    if person_type == models.CustomerPersonType.individual and len(document) != 11:
        raise HTTPException(status_code=422, detail="CPF must have 11 digits")
    if person_type == models.CustomerPersonType.company and len(document) != 14:
        raise HTTPException(status_code=422, detail="CNPJ must have 14 digits")


def _parse_payment_link_config(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _dump_payment_link_config(value: dict | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


def _parse_signup_payload(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _dump_signup_payload(value: dict | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


def _normalize_postal_code(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return None
    if len(digits) != 8:
        raise HTTPException(status_code=422, detail="billing_postal_code must have 8 digits")
    return digits


def _normalize_state(value: str | None) -> str | None:
    cleaned = _normalize_optional_text(value)
    if cleaned is None:
        return None
    normalized = cleaned.upper()
    if len(normalized) != 2:
        raise HTTPException(status_code=422, detail="billing_state must have 2 chars")
    return normalized


def _tenant_out_payload(tenant: models.Tenant) -> TenantOut:
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        users_limit=tenant.users_limit,
        stores_limit=tenant.stores_limit,
        legal_name=tenant.legal_name,
        trade_name=tenant.trade_name,
        state_registration=tenant.state_registration,
        municipal_registration=tenant.municipal_registration,
        contact_name=tenant.contact_name,
        contact_email=tenant.contact_email,
        contact_phone=tenant.contact_phone,
        financial_contact_name=tenant.financial_contact_name,
        financial_contact_email=tenant.financial_contact_email,
        financial_contact_phone=tenant.financial_contact_phone,
        billing_postal_code=tenant.billing_postal_code,
        billing_street=tenant.billing_street,
        billing_number=tenant.billing_number,
        billing_district=tenant.billing_district,
        billing_city=tenant.billing_city,
        billing_state=tenant.billing_state,
        billing_complement=tenant.billing_complement,
        onboarding_origin=tenant.onboarding_origin or "admin_manual",
        activation_mode=tenant.activation_mode or "manual",
        payment_provider=tenant.payment_provider,
        payment_reference=tenant.payment_reference,
        activation_notes=tenant.activation_notes,
        signup_payload=_parse_signup_payload(tenant.signup_payload_json),
        activated_at=tenant.activated_at,
        person_type=tenant.person_type.value if tenant.person_type else None,
        document=tenant.document,
        payment_link_enabled=tenant.payment_link_enabled,
        payment_link_config=_parse_payment_link_config(tenant.payment_link_config),
    )


def _normalize_module_keys(keys: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for key in keys:
        if not key:
            continue
        value = str(key).strip().lower()
        if not value or value in seen:
            continue
        if value in PLAN_IGNORED_MODULE_KEYS:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def _ensure_modules(db: Session, keys: Iterable[str]) -> dict[str, models.Module]:
    normalized = _normalize_module_keys(keys)
    if not normalized:
        return {}
    existing = db.query(models.Module).filter(models.Module.key.in_(normalized)).all()
    by_key = {module.key: module for module in existing}
    missing = [key for key in normalized if key not in by_key]
    for key in missing:
        module = models.Module(
            id=str(uuid.uuid4()),
            key=key,
            name=key.replace("_", " ").title(),
            description=None,
            is_active=True,
        )
        db.add(module)
        by_key[key] = module
    if missing:
        db.flush()
    return by_key


def _plan_modules_keys(plan: models.Plan) -> list[str]:
    modules = []
    for pm in getattr(plan, "modules", []):
        module = getattr(pm, "module", None)
        if module and module.key and module.key not in PLAN_IGNORED_MODULE_KEYS:
            modules.append(module.key)
    return sorted(modules)


def _plan_out_payload(plan: models.Plan) -> PlanOutPayload:
    modules = _plan_modules_keys(plan)
    return PlanOutPayload(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        is_active=plan.is_active,
        price_cents=plan.price_cents,
        currency=plan.currency,
        interval=plan.interval.value if hasattr(plan.interval, "value") else str(plan.interval),
        modules=modules,
    )


def _sync_plan_modules(db: Session, plan_id: str, module_keys: Iterable[str]) -> None:
    normalized = _normalize_module_keys(module_keys)
    module_map = _ensure_modules(db, normalized)
    desired_ids = {module_map[key].id for key in normalized if key in module_map}

    existing_rows = (
        db.query(models.PlanModule)
        .filter(models.PlanModule.plan_id == plan_id)
        .all()
    )
    existing_ids = {row.module_id for row in existing_rows}

    remove_ids = existing_ids - desired_ids
    if remove_ids:
        (
            db.query(models.PlanModule)
            .filter(
                models.PlanModule.plan_id == plan_id,
                models.PlanModule.module_id.in_(remove_ids),
            )
            .delete(synchronize_session=False)
        )

    add_ids = desired_ids - existing_ids
    for module_id in add_ids:
        db.add(models.PlanModule(plan_id=plan_id, module_id=module_id))


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


def _admin_time_range():
    try:
        tz_sp = ZoneInfo("America/Sao_Paulo")
    except ZoneInfoNotFoundError:
        tz_sp = timezone(timedelta(hours=-3))
    now_sp = datetime.now(tz_sp)
    day_start_sp = now_sp.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start_sp = day_start_sp.replace(day=1)
    return (
        day_start_sp.astimezone(timezone.utc),
        month_start_sp.astimezone(timezone.utc),
    )


@router.get("/dashboard", response_model=CentralDashboardOut)
def get_central_dashboard(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    day_start_utc, month_start_utc = _admin_time_range()

    active_tenants_count = (
        db.query(func.count(models.Tenant.id))
        .filter(models.Tenant.status == models.TenantStatus.active)
        .scalar()
    ) or 0

    active_users_now_count = (
        db.query(func.count(models.User.id))
        .filter(
            models.User.is_active.is_(True),
            models.User.last_login_at.isnot(None),
            models.User.last_login_at >= func.now() - text("interval '15 minutes'"),
        )
        .scalar()
    ) or 0

    active_stores_count = (
        db.query(func.count(models.Store.id))
        .filter(models.Store.is_active.is_(True))
        .scalar()
    ) or 0

    orders_today_count = (
        db.query(func.count(models.Order.id))
        .filter(models.Order.created_at >= day_start_utc)
        .scalar()
    ) or 0

    orders_month_count = (
        db.query(func.count(models.Order.id))
        .filter(models.Order.created_at >= month_start_utc)
        .scalar()
    ) or 0

    return CentralDashboardOut(
        active_tenants_count=int(active_tenants_count),
        active_users_now_count=int(active_users_now_count),
        active_stores_count=int(active_stores_count),
        orders_today_count=int(orders_today_count),
        orders_month_count=int(orders_month_count),
    )


@router.post("/tenants", response_model=TenantOut, status_code=201)
def create_tenant(
    payload: TenantCreatePayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    slug = _normalized_slug(payload.slug)
    if not slug:
        raise HTTPException(status_code=400, detail="Slug invalid")

    person_type = _normalize_person_type(payload.person_type)
    document_raw = payload.document or payload.cnpj
    document = _normalize_document(document_raw)
    if document and len(document) not in (11, 14):
        raise HTTPException(status_code=422, detail="Document must be CPF (11) or CNPJ (14)")
    if person_type is None and document:
        if len(document) == 11:
            person_type = models.CustomerPersonType.individual
        elif len(document) == 14:
            person_type = models.CustomerPersonType.company
    if document and person_type:
        _validate_document(person_type, document)
    if payload.payment_link_config is not None and not isinstance(payload.payment_link_config, dict):
        raise HTTPException(status_code=422, detail="payment_link_config must be an object")
    if payload.signup_payload is not None and not isinstance(payload.signup_payload, dict):
        raise HTTPException(status_code=422, detail="signup_payload must be an object")

    plan_id = payload.plan.strip() if payload.plan else None
    if plan_id:
        plan = (
            db.query(models.Plan)
            .filter(models.Plan.id == plan_id, models.Plan.is_active.is_(True))
            .first()
        )
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found or inactive")

    existing = (
        db.query(models.Tenant)
        .filter(func.lower(models.Tenant.slug) == slug)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Tenant already exists")

    try:
        status_value = models.TenantStatus(payload.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    contact_phone = normalize_phone(payload.contact_phone) or None
    financial_contact_phone = normalize_phone(payload.financial_contact_phone) or None

    tenant = models.Tenant(
        id=str(uuid.uuid4()),
        name=payload.name.strip(),
        slug=slug,
        status=status_value,
        users_limit=payload.users_limit,
        stores_limit=payload.stores_limit,
        legal_name=_normalize_optional_text(payload.legal_name),
        trade_name=_normalize_optional_text(payload.trade_name),
        state_registration=_normalize_optional_text(payload.state_registration),
        municipal_registration=_normalize_optional_text(payload.municipal_registration),
        contact_name=_normalize_optional_text(payload.contact_name),
        contact_email=_normalize_optional_text(str(payload.contact_email)) if payload.contact_email else None,
        contact_phone=contact_phone,
        financial_contact_name=_normalize_optional_text(payload.financial_contact_name),
        financial_contact_email=(
            _normalize_optional_text(str(payload.financial_contact_email)) if payload.financial_contact_email else None
        ),
        financial_contact_phone=financial_contact_phone,
        billing_postal_code=_normalize_postal_code(payload.billing_postal_code),
        billing_street=_normalize_optional_text(payload.billing_street),
        billing_number=_normalize_optional_text(payload.billing_number),
        billing_district=_normalize_optional_text(payload.billing_district),
        billing_city=_normalize_optional_text(payload.billing_city),
        billing_state=_normalize_state(payload.billing_state),
        billing_complement=_normalize_optional_text(payload.billing_complement),
        onboarding_origin=_normalize_optional_text(payload.onboarding_origin) or "admin_manual",
        activation_mode=_normalize_optional_text(payload.activation_mode) or "manual",
        payment_provider=_normalize_optional_text(payload.payment_provider),
        payment_reference=_normalize_optional_text(payload.payment_reference),
        activation_notes=_normalize_optional_text(payload.activation_notes),
        signup_payload_json=_dump_signup_payload(payload.signup_payload),
        activated_at=payload.activated_at,
        person_type=person_type or models.CustomerPersonType.company,
        document=document,
        payment_link_enabled=bool(payload.payment_link_enabled),
        payment_link_config=_dump_payment_link_config(payload.payment_link_config),
    )
    db.add(tenant)
    try:
        db.commit()
    except DataError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="Dados invalidos para cadastro. Verifique principalmente o CEP de cobranca (8 digitos).",
        ) from exc
    db.refresh(tenant)
    if plan_id:
        assign_plan_to_tenant(db, tenant.id, plan_id)
    return _tenant_out_payload(tenant)


@router.get("/tenants", response_model=list[TenantListOut])
def list_tenants(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    users_count = (
        db.query(models.User.tenant_id, func.count(models.User.id).label("users_count"))
        .group_by(models.User.tenant_id)
        .subquery()
    )
    stores_count = (
        db.query(models.Store.tenant_id, func.count(models.Store.id).label("stores_count"))
        .group_by(models.Store.tenant_id)
        .subquery()
    )
    rows = (
        db.query(
            models.Tenant,
            func.coalesce(users_count.c.users_count, 0),
            func.coalesce(stores_count.c.stores_count, 0),
        )
        .outerjoin(users_count, users_count.c.tenant_id == models.Tenant.id)
        .outerjoin(stores_count, stores_count.c.tenant_id == models.Tenant.id)
        .order_by(models.Tenant.created_at.desc())
        .all()
    )
    output: list[TenantListOut] = []
    for tenant, users_used, stores_used in rows:
        output.append(
            TenantListOut(
                id=tenant.id,
                name=tenant.name,
                slug=tenant.slug,
                status=getattr(tenant.status, "value", str(tenant.status)),
                users_limit=tenant.users_limit,
                stores_limit=tenant.stores_limit,
                legal_name=tenant.legal_name,
                trade_name=tenant.trade_name,
                state_registration=tenant.state_registration,
                municipal_registration=tenant.municipal_registration,
                contact_name=tenant.contact_name,
                contact_email=tenant.contact_email,
                contact_phone=tenant.contact_phone,
                financial_contact_name=tenant.financial_contact_name,
                financial_contact_email=tenant.financial_contact_email,
                financial_contact_phone=tenant.financial_contact_phone,
                billing_postal_code=tenant.billing_postal_code,
                billing_street=tenant.billing_street,
                billing_number=tenant.billing_number,
                billing_district=tenant.billing_district,
                billing_city=tenant.billing_city,
                billing_state=tenant.billing_state,
                billing_complement=tenant.billing_complement,
                onboarding_origin=tenant.onboarding_origin or "admin_manual",
                activation_mode=tenant.activation_mode or "manual",
                payment_provider=tenant.payment_provider,
                payment_reference=tenant.payment_reference,
                activation_notes=tenant.activation_notes,
                signup_payload=_parse_signup_payload(tenant.signup_payload_json),
                activated_at=tenant.activated_at,
                users_count=int(users_used or 0),
                stores_count=int(stores_used or 0),
                created_at=tenant.created_at.isoformat(),
                person_type=tenant.person_type.value if tenant.person_type else None,
                document=tenant.document,
                payment_link_enabled=tenant.payment_link_enabled,
                payment_link_config=_parse_payment_link_config(tenant.payment_link_config),
            )
        )
    return output


@router.patch("/tenants/{tenant_slug}", response_model=TenantOut)
def update_tenant(
    tenant_slug: str,
    payload: TenantUpdatePayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")

    if payload.slug:
        slug = _normalized_slug(payload.slug)
        exists = (
            db.query(models.Tenant)
            .filter(func.lower(models.Tenant.slug) == slug, models.Tenant.id != tenant.id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="Tenant already exists")
        tenant.slug = slug
    if payload.name is not None:
        tenant.name = payload.name.strip()
    if payload.status is not None:
        try:
            tenant.status = models.TenantStatus(payload.status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    if payload.users_limit is not None:
        tenant.users_limit = payload.users_limit
    if "stores_limit" in payload.model_fields_set:
        tenant.stores_limit = payload.stores_limit
    if "legal_name" in payload.model_fields_set:
        tenant.legal_name = _normalize_optional_text(payload.legal_name)
    if "trade_name" in payload.model_fields_set:
        tenant.trade_name = _normalize_optional_text(payload.trade_name)
    if "state_registration" in payload.model_fields_set:
        tenant.state_registration = _normalize_optional_text(payload.state_registration)
    if "municipal_registration" in payload.model_fields_set:
        tenant.municipal_registration = _normalize_optional_text(payload.municipal_registration)
    if "contact_name" in payload.model_fields_set:
        tenant.contact_name = _normalize_optional_text(payload.contact_name)
    if "contact_email" in payload.model_fields_set:
        tenant.contact_email = _normalize_optional_text(str(payload.contact_email)) if payload.contact_email else None
    if "contact_phone" in payload.model_fields_set:
        tenant.contact_phone = normalize_phone(payload.contact_phone) or None
    if "financial_contact_name" in payload.model_fields_set:
        tenant.financial_contact_name = _normalize_optional_text(payload.financial_contact_name)
    if "financial_contact_email" in payload.model_fields_set:
        tenant.financial_contact_email = (
            _normalize_optional_text(str(payload.financial_contact_email)) if payload.financial_contact_email else None
        )
    if "financial_contact_phone" in payload.model_fields_set:
        tenant.financial_contact_phone = normalize_phone(payload.financial_contact_phone) or None
    if "billing_postal_code" in payload.model_fields_set:
        tenant.billing_postal_code = _normalize_postal_code(payload.billing_postal_code)
    if "billing_street" in payload.model_fields_set:
        tenant.billing_street = _normalize_optional_text(payload.billing_street)
    if "billing_number" in payload.model_fields_set:
        tenant.billing_number = _normalize_optional_text(payload.billing_number)
    if "billing_district" in payload.model_fields_set:
        tenant.billing_district = _normalize_optional_text(payload.billing_district)
    if "billing_city" in payload.model_fields_set:
        tenant.billing_city = _normalize_optional_text(payload.billing_city)
    if "billing_state" in payload.model_fields_set:
        tenant.billing_state = _normalize_state(payload.billing_state)
    if "billing_complement" in payload.model_fields_set:
        tenant.billing_complement = _normalize_optional_text(payload.billing_complement)
    if "onboarding_origin" in payload.model_fields_set:
        tenant.onboarding_origin = _normalize_optional_text(payload.onboarding_origin) or "admin_manual"
    if "activation_mode" in payload.model_fields_set:
        tenant.activation_mode = _normalize_optional_text(payload.activation_mode) or "manual"
    if "payment_provider" in payload.model_fields_set:
        tenant.payment_provider = _normalize_optional_text(payload.payment_provider)
    if "payment_reference" in payload.model_fields_set:
        tenant.payment_reference = _normalize_optional_text(payload.payment_reference)
    if "activation_notes" in payload.model_fields_set:
        tenant.activation_notes = _normalize_optional_text(payload.activation_notes)
    if "signup_payload" in payload.model_fields_set:
        if payload.signup_payload is not None and not isinstance(payload.signup_payload, dict):
            raise HTTPException(status_code=422, detail="signup_payload must be an object")
        tenant.signup_payload_json = _dump_signup_payload(payload.signup_payload)
    if "activated_at" in payload.model_fields_set:
        tenant.activated_at = payload.activated_at
    if payload.person_type is not None:
        person_type = _normalize_person_type(payload.person_type)
        if person_type is None:
            raise HTTPException(status_code=422, detail="Invalid person_type")
        tenant.person_type = person_type
    if "document" in payload.model_fields_set:
        document = _normalize_document(payload.document)
        if document:
            if len(document) not in (11, 14):
                raise HTTPException(status_code=422, detail="Document must be CPF (11) or CNPJ (14)")
            person_type = tenant.person_type
            _validate_document(person_type, document)
        tenant.document = document
    if payload.payment_link_enabled is not None:
        tenant.payment_link_enabled = payload.payment_link_enabled
    if "payment_link_config" in payload.model_fields_set:
        if payload.payment_link_config is not None and not isinstance(payload.payment_link_config, dict):
            raise HTTPException(status_code=422, detail="payment_link_config must be an object")
        tenant.payment_link_config = _dump_payment_link_config(payload.payment_link_config)

    try:
        db.commit()
    except DataError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="Dados invalidos para atualizacao. Verifique principalmente o CEP de cobranca (8 digitos).",
        ) from exc
    db.refresh(tenant)
    return _tenant_out_payload(tenant)


@router.post("/tenants/{tenant_slug}/onboarding-test-enable")
def enable_tenant_onboarding_test(
    tenant_slug: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    tenant.activation_mode = ONBOARDING_FORCE_TEST_MODE
    db.commit()
    return {"ok": True, "tenant_slug": tenant.slug, "activation_mode": tenant.activation_mode}


@router.post("/users", status_code=201)
def create_user_for_tenant(
    payload: UserCreatePayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=payload.tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")

    email = payload.email.strip().lower()
    existing = (
        db.query(models.User)
        .filter(
            models.User.tenant_id == tenant.id,
            func.lower(models.User.email) == email,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email ja em uso")

    try:
        role = models.UserRole(payload.role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")

    default_store_id = payload.default_store_id
    if default_store_id:
        store = (
            db.query(models.Store)
            .filter(models.Store.id == default_store_id, models.Store.tenant_id == tenant.id)
            .first()
        )
        if not store:
            raise HTTPException(status_code=404, detail="Loja nao encontrada")

    user = models.User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=role,
        max_active_sessions=normalize_max_active_sessions(payload.max_active_sessions),
        default_store_id=default_store_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "tenant_id": tenant.id}


@router.patch("/tenants/{tenant_slug}/limits")
def update_tenant_limits(
    tenant_slug: str,
    payload: LimitsPayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    tenant.users_limit = payload.users_limit
    if "stores_limit" in payload.model_fields_set:
        tenant.stores_limit = payload.stores_limit
    db.commit()
    return {"ok": True, "users_limit": tenant.users_limit, "stores_limit": tenant.stores_limit}


@router.put("/tenants/{tenant_slug}/modules")
def replace_tenant_modules(
    tenant_slug: str,
    payload: ModulesPayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    keys = [key.strip() for key in payload.modules if key and key.strip()]
    sync_tenant_modules(db, tenant.id, keys)
    return {"ok": True, "modules": keys}


@router.get("/tenants/{tenant_slug}/modules")
def get_tenant_modules(
    tenant_slug: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    modules = (
        db.query(models.TenantModule.module)
        .filter(models.TenantModule.tenant_id == tenant.id)
        .order_by(models.TenantModule.module.asc())
        .all()
    )
    return {"modules": [row[0] for row in modules]}


@router.get("/plans", response_model=list[PlanOutPayload])
def list_plans(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    plans = (
        db.query(models.Plan)
        .options(joinedload(models.Plan.modules).joinedload(models.PlanModule.module))
        .order_by(models.Plan.name.asc())
        .all()
    )
    return [_plan_out_payload(plan) for plan in plans]


@router.post("/plans", response_model=PlanOutPayload, status_code=201)
def create_plan(
    payload: PlanCreatePayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    exists = (
        db.query(models.Plan.id)
        .filter(func.lower(models.Plan.name) == name.lower())
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Plan name already exists")

    interval_value = None
    if payload.interval:
        try:
            interval_value = models.PlanInterval(payload.interval)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid interval")

    plan = models.Plan(
        id=str(uuid.uuid4()),
        name=name,
        description=payload.description,
        is_active=payload.is_active,
        price_cents=payload.price_cents if payload.price_cents is not None else 0,
        currency=(payload.currency or "BRL").upper(),
        interval=interval_value or models.PlanInterval.monthly,
    )
    db.add(plan)
    db.flush()
    _sync_plan_modules(db, plan.id, payload.module_keys)
    db.commit()
    db.refresh(plan)
    plan = (
        db.query(models.Plan)
        .options(joinedload(models.Plan.modules).joinedload(models.PlanModule.module))
        .filter(models.Plan.id == plan.id)
        .first()
    )
    return _plan_out_payload(plan)


@router.patch("/plans/{plan_id}", response_model=PlanOutPayload)
def update_plan(
    plan_id: str,
    payload: PlanUpdatePayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    plan = (
        db.query(models.Plan)
        .options(joinedload(models.Plan.modules).joinedload(models.PlanModule.module))
        .filter(models.Plan.id == plan_id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        exists = (
            db.query(models.Plan.id)
            .filter(func.lower(models.Plan.name) == name.lower(), models.Plan.id != plan.id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="Plan name already exists")
        plan.name = name

    if payload.description is not None:
        plan.description = payload.description
    if payload.is_active is not None:
        plan.is_active = payload.is_active
    if payload.price_cents is not None:
        plan.price_cents = payload.price_cents
    if payload.currency is not None:
        plan.currency = payload.currency.upper()
    if payload.interval is not None:
        try:
            plan.interval = models.PlanInterval(payload.interval)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid interval")

    if payload.module_keys is not None:
        _sync_plan_modules(db, plan.id, payload.module_keys)

    db.commit()
    db.refresh(plan)
    plan = (
        db.query(models.Plan)
        .options(joinedload(models.Plan.modules).joinedload(models.PlanModule.module))
        .filter(models.Plan.id == plan.id)
        .first()
    )
    return _plan_out_payload(plan)


@router.get("/tenants/{tenant_slug}/plan", response_model=TenantPlanOut)
def get_tenant_plan(
    tenant_slug: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    subscription = (
        db.query(models.Subscription)
        .filter(models.Subscription.tenant_id == tenant.id)
        .first()
    )
    if not subscription:
        return TenantPlanOut()
    plan = (
        db.query(models.Plan)
        .options(joinedload(models.Plan.modules).joinedload(models.PlanModule.module))
        .filter(models.Plan.id == subscription.plan_id)
        .first()
    )
    modules = _plan_modules_keys(plan) if plan else []
    return TenantPlanOut(
        plan_id=subscription.plan_id,
        plan_name=plan.name if plan else None,
        status=subscription.status.value if hasattr(subscription.status, "value") else str(subscription.status),
        modules=modules,
    )


@router.put("/tenants/{tenant_slug}/plan", response_model=TenantPlanOut)
def update_tenant_plan(
    tenant_slug: str,
    payload: TenantPlanPayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")

    plan_id = payload.plan_id.strip()
    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required")

    subscription = assign_plan_to_tenant(db, tenant.id, plan_id)
    plan = (
        db.query(models.Plan)
        .options(joinedload(models.Plan.modules).joinedload(models.PlanModule.module))
        .filter(models.Plan.id == subscription.plan_id)
        .first()
    )
    modules = _plan_modules_keys(plan) if plan else []
    return TenantPlanOut(
        plan_id=subscription.plan_id,
        plan_name=plan.name if plan else None,
        status=subscription.status.value if hasattr(subscription.status, "value") else str(subscription.status),
        modules=modules,
    )


@router.get("/tenants/{tenant_slug}/messaging", response_model=MessagingConfigPayload)
def get_tenant_messaging_config(
    tenant_slug: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    cfg = _get_or_create_config(db, tenant.id)
    return MessagingConfigPayload(
        whatsapp_enabled=cfg.whatsapp_enabled,
        whatsapp_token=_mask_token(cfg.whatsapp_token),
        whatsapp_phone_number_id=cfg.whatsapp_phone_number_id,
        telegram_enabled=cfg.telegram_enabled,
        telegram_bot_token=_mask_token(cfg.telegram_bot_token),
        telegram_chat_id=cfg.telegram_chat_id,
    )


@router.patch("/tenants/{tenant_slug}/messaging", response_model=MessagingConfigPayload)
def update_tenant_messaging_config(
    tenant_slug: str,
    payload: MessagingConfigPayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    cfg = _get_or_create_config(db, tenant.id)
    if payload.whatsapp_enabled is not None:
        cfg.whatsapp_enabled = payload.whatsapp_enabled
    if payload.whatsapp_token is not None:
        normalized = _normalize_optional_text(payload.whatsapp_token)
        if normalized and normalized != "••••••••" and len(normalized) < 20:
            raise HTTPException(status_code=400, detail="WhatsApp token muito curto")
        if normalized and normalized != "••••••••":
            cfg.whatsapp_token = normalized
    if payload.whatsapp_phone_number_id is not None:
        normalized = _normalize_optional_text(payload.whatsapp_phone_number_id)
        if normalized:
            if not PHONE_NUMBER_ID_RE.match(normalized):
                raise HTTPException(status_code=400, detail="Phone number id invalido")
            conflict = (
                db.query(models.OperationsConfig)
                .filter(models.OperationsConfig.whatsapp_phone_number_id == normalized)
                .filter(models.OperationsConfig.tenant_id != tenant.id)
                .first()
            )
            if conflict:
                raise HTTPException(status_code=400, detail="Numero do WhatsApp ja vinculado a outro tenant")
        cfg.whatsapp_phone_number_id = normalized
    if payload.telegram_enabled is not None:
        cfg.telegram_enabled = payload.telegram_enabled
    if payload.telegram_bot_token is not None:
        normalized = _normalize_optional_text(payload.telegram_bot_token)
        if normalized and normalized != "••••••••" and len(normalized) < 20:
            raise HTTPException(status_code=400, detail="Telegram token muito curto")
        if normalized and normalized != "••••••••":
            cfg.telegram_bot_token = normalized
    if payload.telegram_chat_id is not None:
        cfg.telegram_chat_id = _normalize_optional_text(payload.telegram_chat_id)
    db.commit()
    return MessagingConfigPayload(
        whatsapp_enabled=cfg.whatsapp_enabled,
        whatsapp_token=_mask_token(cfg.whatsapp_token),
        whatsapp_phone_number_id=cfg.whatsapp_phone_number_id,
        telegram_enabled=cfg.telegram_enabled,
        telegram_bot_token=_mask_token(cfg.telegram_bot_token),
        telegram_chat_id=cfg.telegram_chat_id,
    )


class UserUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    role: str | None = None
    is_active: bool | None = None
    max_active_sessions: int | None = Field(default=None, ge=1, le=20)
    default_store_id: str | None = None


class TenantScopedUserCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default=models.UserRole.operator.value)
    max_active_sessions: int = Field(default=3, ge=1, le=20)
    default_store_id: str | None = None


@router.get("/tenants/{tenant_slug}/users", response_model=list[schemas.UserOut])
def list_tenant_users(
    tenant_slug: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    return (
        db.query(models.User)
        .filter(models.User.tenant_id == tenant.id)
        .order_by(models.User.created_at.asc())
        .all()
    )


@router.post("/tenants/{tenant_slug}/users", response_model=schemas.UserOut, status_code=201)
def create_tenant_user(
    tenant_slug: str,
    payload: TenantScopedUserCreatePayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")

    used = (
        db.query(func.count(models.User.id))
        .filter(models.User.tenant_id == tenant.id)
        .scalar()
    )
    if used >= tenant.users_limit:
        raise HTTPException(status_code=400, detail="Licencas esgotadas para este tenant")

    email = payload.email.strip().lower()
    existing = (
        db.query(models.User)
        .filter(
            models.User.tenant_id == tenant.id,
            func.lower(models.User.email) == email,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email ja em uso")

    try:
        role = models.UserRole(payload.role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")

    default_store_id = payload.default_store_id
    if default_store_id:
        store = (
            db.query(models.Store)
            .filter(models.Store.id == default_store_id, models.Store.tenant_id == tenant.id)
            .first()
        )
        if not store:
            raise HTTPException(status_code=404, detail="Loja nao encontrada")

    user = models.User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=role,
        max_active_sessions=normalize_max_active_sessions(payload.max_active_sessions),
        default_store_id=default_store_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/tenants/{tenant_slug}/users/{user_id}", response_model=schemas.UserOut)
def update_tenant_user(
    tenant_slug: str,
    user_id: str,
    payload: UserUpdatePayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_super_admin),
):
    tenant = resolve_tenant(db, tenant_id=None, tenant_slug=tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant nao encontrado")
    user = (
        db.query(models.User)
        .filter(models.User.id == user_id, models.User.tenant_id == tenant.id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.email is not None:
        email = payload.email.strip().lower()
        exists = (
            db.query(models.User)
            .filter(
                models.User.tenant_id == tenant.id,
                func.lower(models.User.email) == email,
                models.User.id != user.id,
            )
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="Email ja em uso")
        user.email = email
    if payload.role is not None:
        try:
            user.role = models.UserRole(payload.role)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid role")
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.max_active_sessions is not None:
        user.max_active_sessions = normalize_max_active_sessions(payload.max_active_sessions)
        trim_user_sessions_to_limit(db, user=user, tenant_id=tenant.id)
    if payload.default_store_id is not None:
        if payload.default_store_id:
            store = (
                db.query(models.Store)
                .filter(models.Store.id == payload.default_store_id, models.Store.tenant_id == tenant.id)
                .first()
            )
            if not store:
                raise HTTPException(status_code=404, detail="Loja nao encontrada")
        user.default_store_id = payload.default_store_id

    db.commit()
    db.refresh(user)
    return user

