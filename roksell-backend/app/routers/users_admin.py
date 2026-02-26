import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import require_roles
from app.db import get_db
from app.domain.tenancy.access import load_json_list
from app.security import hash_password
from app.services.user_sessions import normalize_max_active_sessions, trim_user_sessions_to_limit
from app.tenancy import TenantContext, get_tenant_context

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _tenant_store_ids(db: Session, tenant_id: str) -> list[str]:
    rows = (
        db.query(models.Store.id)
        .filter(models.Store.tenant_id == tenant_id)
        .all()
    )
    return [row[0] for row in rows]


def _validate_group(db: Session, tenant_id: str, group_id: str | None) -> models.UserGroup:
    if not group_id:
        raise HTTPException(status_code=400, detail="group_id is required")
    group = (
        db.query(models.UserGroup)
        .filter(
            models.UserGroup.id == group_id,
            models.UserGroup.tenant_id == tenant_id,
            models.UserGroup.is_active.is_(True),
        )
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def _allowed_store_ids_for_group(db: Session, tenant_id: str, group: models.UserGroup) -> list[str]:
    tenant_store_ids = _tenant_store_ids(db, tenant_id)
    configured_store_ids = set(load_json_list(group.store_ids_json))
    if not configured_store_ids:
        return tenant_store_ids
    return [store_id for store_id in tenant_store_ids if store_id in configured_store_ids]


def _validate_store(db: Session, tenant_id: str, store_id: str | None, allowed_store_ids: list[str]) -> str | None:
    if not store_id:
        return None
    store = (
        db.query(models.Store)
        .filter(models.Store.id == store_id, models.Store.tenant_id == tenant_id)
        .first()
    )
    if not store:
        raise HTTPException(status_code=404, detail="Loja nao encontrada")
    if allowed_store_ids and store.id not in allowed_store_ids:
        raise HTTPException(status_code=400, detail="Loja fora do escopo do grupo")
    return store.id


@router.get("", response_model=list[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    return (
        db.query(models.User)
        .filter(models.User.tenant_id == tenant.id)
        .order_by(models.User.created_at.asc())
        .all()
    )


@router.post("", response_model=schemas.UserOut, status_code=201)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner)),
):
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

    group = _validate_group(db, tenant.id, payload.group_id)
    allowed_store_ids = _allowed_store_ids_for_group(db, tenant.id, group)
    default_store_id = _validate_store(db, tenant.id, payload.default_store_id, allowed_store_ids)

    user = models.User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        group_id=group.id,
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


@router.get("/limits", response_model=schemas.UserLicensesOut)
def users_limits(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    used = (
        db.query(func.count(models.User.id))
        .filter(models.User.tenant_id == tenant.id)
        .scalar()
    )
    return schemas.UserLicensesOut(limit=tenant.users_limit, used=used)


@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: str,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner)),
):
    user = (
        db.query(models.User)
        .filter(models.User.id == user_id, models.User.tenant_id == tenant.id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    group = None
    if payload.group_id is not None:
        group = _validate_group(db, tenant.id, payload.group_id)
        user.group_id = group.id
    elif user.group_id:
        group = _validate_group(db, tenant.id, user.group_id)

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
        allowed_store_ids = _allowed_store_ids_for_group(db, tenant.id, group) if group else _tenant_store_ids(db, tenant.id)
        user.default_store_id = _validate_store(db, tenant.id, payload.default_store_id, allowed_store_ids)
    elif payload.group_id is not None and group is not None:
        allowed_store_ids = _allowed_store_ids_for_group(db, tenant.id, group)
        if user.default_store_id and allowed_store_ids and user.default_store_id not in allowed_store_ids:
            user.default_store_id = None

    db.commit()
    db.refresh(user)
    return user
