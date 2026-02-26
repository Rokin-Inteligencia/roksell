import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import require_roles
from app.db import get_db
from app.domain.tenancy.access import (
    MODULE_PERMISSION_ACTIONS,
    dump_json_list,
    load_json_list,
    normalize_tenant_modules,
    split_module_permission,
    user_accessible_store_ids,
)
from app.tenancy import TenantContext, get_tenant_context

router = APIRouter(prefix="/admin/groups", tags=["admin-groups"])


def _tenant_store_ids(db: Session, tenant_id: str) -> list[str]:
    rows = (
        db.query(models.Store.id)
        .filter(models.Store.tenant_id == tenant_id)
        .all()
    )
    return [row[0] for row in rows]


def _normalize_store_ids(db: Session, tenant_id: str, store_ids: list[str] | None) -> list[str]:
    tenant_store_ids = _tenant_store_ids(db, tenant_id)
    if not tenant_store_ids:
        return []

    values = [item for item in (store_ids or []) if item]
    if not values:
        if len(tenant_store_ids) == 1:
            return [tenant_store_ids[0]]
        raise HTTPException(status_code=400, detail="store_ids is required when tenant has multiple stores")

    invalid = [item for item in values if item not in tenant_store_ids]
    if invalid:
        raise HTTPException(status_code=400, detail="store_ids contains invalid store")
    unique: list[str] = []
    for item in values:
        if item not in unique:
            unique.append(item)
    return unique


def _normalize_permissions(tenant: TenantContext, permissions: list[str] | None) -> list[str]:
    available_modules = normalize_tenant_modules(tenant.modules)
    values = [item for item in (permissions or []) if item]
    unique: list[str] = []
    invalid: list[str] = []
    for item in values:
        module_key, action = split_module_permission(item)
        if not module_key or module_key not in available_modules:
            invalid.append(str(item))
            continue
        if action is not None and action not in MODULE_PERMISSION_ACTIONS:
            invalid.append(str(item))
            continue
        normalized = f"{module_key}:{action}" if action else module_key
        if normalized not in unique:
            unique.append(normalized)
    if invalid:
        raise HTTPException(status_code=400, detail="permissions contains invalid module/action")
    return unique


def _group_out(db: Session, group: models.UserGroup) -> schemas.GroupOut:
    used = (
        db.query(func.count(models.User.id))
        .filter(models.User.tenant_id == group.tenant_id, models.User.group_id == group.id)
        .scalar()
    ) or 0
    return schemas.GroupOut(
        id=group.id,
        name=group.name,
        is_active=group.is_active,
        permissions=load_json_list(group.permissions_json),
        store_ids=load_json_list(group.store_ids_json),
        users_count=int(used),
    )


@router.get("", response_model=list[schemas.GroupOut])
def list_groups(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    groups = (
        db.query(models.UserGroup)
        .filter(models.UserGroup.tenant_id == tenant.id)
        .order_by(models.UserGroup.created_at.asc())
        .all()
    )
    return [_group_out(db, group) for group in groups]


@router.get("/options", response_model=schemas.GroupOptionsOut)
def group_options(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    user: models.User = Depends(
        require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)
    ),
):
    allowed_store_ids = set(user_accessible_store_ids(db=db, tenant_id=tenant.id, user=user))
    store_rows = (
        db.query(models.Store.id, models.Store.name, models.Store.slug)
        .filter(models.Store.tenant_id == tenant.id, models.Store.id.in_(allowed_store_ids))
        .order_by(models.Store.name.asc())
        .all()
    )
    subscription = (
        db.query(models.Subscription)
        .filter(models.Subscription.tenant_id == tenant.id)
        .first()
    )
    plan = None
    if subscription:
        plan = db.query(models.Plan).filter(models.Plan.id == subscription.plan_id).first()
    return schemas.GroupOptionsOut(
        modules=sorted(normalize_tenant_modules(tenant.modules)),
        stores=[
            schemas.GroupStoreOptionOut(id=row[0], name=row[1], slug=row[2])
            for row in store_rows
        ],
        active_plan_name=plan.name if plan else None,
        active_plan_id=plan.id if plan else None,
    )


@router.post("", response_model=schemas.GroupOut, status_code=201)
def create_group(
    payload: schemas.GroupCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner)),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    exists = (
        db.query(models.UserGroup)
        .filter(models.UserGroup.tenant_id == tenant.id, models.UserGroup.name == name)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Group already exists")

    permissions = _normalize_permissions(tenant, payload.permissions)
    store_ids = _normalize_store_ids(db, tenant.id, payload.store_ids)

    group = models.UserGroup(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        name=name,
        permissions_json=dump_json_list(permissions),
        store_ids_json=dump_json_list(store_ids),
        is_active=payload.is_active,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return _group_out(db, group)


@router.patch("/{group_id}", response_model=schemas.GroupOut)
def update_group(
    group_id: str,
    payload: schemas.GroupUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner)),
):
    group = (
        db.query(models.UserGroup)
        .filter(models.UserGroup.id == group_id, models.UserGroup.tenant_id == tenant.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        duplicate = (
            db.query(models.UserGroup)
            .filter(
                models.UserGroup.tenant_id == tenant.id,
                models.UserGroup.name == name,
                models.UserGroup.id != group.id,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=400, detail="Group already exists")
        group.name = name

    if payload.permissions is not None:
        permissions = _normalize_permissions(tenant, payload.permissions)
        group.permissions_json = dump_json_list(permissions)

    if payload.store_ids is not None:
        store_ids = _normalize_store_ids(db, tenant.id, payload.store_ids)
        group.store_ids_json = dump_json_list(store_ids)

    if payload.is_active is not None:
        group.is_active = payload.is_active

    db.commit()
    db.refresh(group)
    return _group_out(db, group)


@router.delete("/{group_id}", status_code=204)
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner)),
):
    group = (
        db.query(models.UserGroup)
        .filter(models.UserGroup.id == group_id, models.UserGroup.tenant_id == tenant.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    in_use = (
        db.query(models.User.id)
        .filter(models.User.tenant_id == tenant.id, models.User.group_id == group.id)
        .first()
    )
    if in_use:
        raise HTTPException(status_code=400, detail="Group has linked users")
    db.delete(group)
    db.commit()
