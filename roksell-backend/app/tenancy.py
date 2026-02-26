from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app import models

LEGACY_TENANT_ID = "00000000-0000-0000-0000-000000000001"
LEGACY_TENANT_SLUG = "legacy"


@dataclass(frozen=True, slots=True)
class TenantContext:
    id: str
    slug: str
    subscription_status: str
    modules: frozenset[str]
    users_limit: int
    stores_limit: int | None
    name: str


def _modules_to_set(rows: Iterable[str | models.TenantModule]) -> frozenset[str]:
    values: set[str] = set()
    for row in rows:
        if isinstance(row, str):
            values.add(row)
        else:
            values.add(getattr(row, "module"))
    return frozenset(values)


def _resolve_tenant(db: Session, tenant_id: str | None, tenant_slug: str | None) -> models.Tenant | None:
    query = db.query(models.Tenant)
    if tenant_id:
        return query.filter(models.Tenant.id == tenant_id).first()
    if tenant_slug:
        slug = tenant_slug.strip().lower()
        if slug:
            return query.filter(func.lower(models.Tenant.slug) == slug).first()
    return query.filter(models.Tenant.id == LEGACY_TENANT_ID).first()


def resolve_tenant(db: Session, tenant_id: str | None, tenant_slug: str | None) -> models.Tenant | None:
    return _resolve_tenant(db, tenant_id=tenant_id, tenant_slug=tenant_slug)


def build_tenant_context(db: Session, tenant: models.Tenant) -> TenantContext:
    subscription = (
        db.query(models.Subscription)
        .filter(models.Subscription.tenant_id == tenant.id)
        .first()
    )
    modules_query = (
        db.query(models.TenantModule.module)
        .filter(models.TenantModule.tenant_id == tenant.id)
        .all()
    )
    subscription_status = subscription.status.value if subscription else "active"
    if subscription_status not in ("active", "trialing"):
        modules_query = []
    modules = modules_query
    return TenantContext(
        id=tenant.id,
        slug=tenant.slug,
        subscription_status=subscription_status,
        modules=_modules_to_set(modules),
        users_limit=getattr(tenant, "users_limit", 5),
        stores_limit=getattr(tenant, "stores_limit", None),
        name=getattr(tenant, "name", tenant.slug),
    )


def get_tenant_context(
    db: Session = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_tenant: str | None = Header(default=None, alias="X-Tenant"),
) -> TenantContext:
    tenant = _resolve_tenant(db, tenant_id=x_tenant_id, tenant_slug=x_tenant)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    return build_tenant_context(db, tenant)


def legacy_tenant_id() -> str:
    """Útil em scripts/migrations enquanto não existe resolução dinâmica."""
    return LEGACY_TENANT_ID
