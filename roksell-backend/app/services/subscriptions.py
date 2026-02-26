import uuid
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models
from app.domain.billing.enums import SubscriptionStatus
from app.domain.tenancy.access import normalize_tenant_modules


def _module_keys_from_plan(plan: models.Plan) -> set[str]:
    return {pm.module.key for pm in plan.modules if pm.module.is_active}


def sync_tenant_modules(
    db: Session,
    tenant_id: str,
    module_keys: Iterable[str],
    *,
    auto_commit: bool = True,
) -> None:
    normalized_keys = sorted(normalize_tenant_modules(list(module_keys)))
    db.query(models.TenantModule).filter(models.TenantModule.tenant_id == tenant_id).delete()
    for key in normalized_keys:
        db.add(
            models.TenantModule(
                tenant_id=tenant_id,
                module=key,
            )
        )
    if auto_commit:
        db.commit()


def assign_plan_to_tenant(db: Session, tenant_id: str, plan_id: str) -> models.Subscription:
    plan = (
        db.query(models.Plan)
        .options(joinedload(models.Plan.modules).joinedload(models.PlanModule.module))
        .filter(
            models.Plan.id == plan_id,
            models.Plan.is_active.is_(True),
        )
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found or inactive")

    subscription = (
        db.query(models.Subscription)
        .filter(models.Subscription.tenant_id == tenant_id)
        .first()
    )

    module_keys = _module_keys_from_plan(plan)

    if subscription:
        subscription.plan_id = plan.id
        subscription.status = SubscriptionStatus.active
    else:
        subscription = models.Subscription(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            plan_id=plan.id,
            status=SubscriptionStatus.active,
        )
        db.add(subscription)

    sync_tenant_modules(db, tenant_id, module_keys, auto_commit=False)
    db.commit()
    db.refresh(subscription)
    return subscription
