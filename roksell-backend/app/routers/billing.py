from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app import models
from app.auth.dependencies import require_roles
from app.db import get_db
from app.schemas import SubscriptionOut, PlanOut
from app.services.subscriptions import assign_plan_to_tenant
from app.tenancy import TenantContext, get_tenant_context

router = APIRouter(prefix="/admin/billing", tags=["billing"])


@router.get("/plans", response_model=List[PlanOut])
def list_plans(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(models.UserRole.owner)),
):
    plans = (
        db.query(models.Plan)
        .options(joinedload(models.Plan.modules).joinedload(models.PlanModule.module))
        .filter(models.Plan.is_active.is_(True))
        .order_by(models.Plan.price_cents.asc())
        .all()
    )
    return [
        PlanOut(
            id=plan.id,
            name=plan.name,
            price_cents=plan.price_cents,
            currency=plan.currency,
            interval=plan.interval.value,
            description=plan.description,
            modules=[pm.module.key for pm in plan.modules if pm.module.is_active],
        )
        for plan in plans
    ]


@router.get("/subscription", response_model=SubscriptionOut)
def get_subscription(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    subscription = (
        db.query(models.Subscription)
        .filter(models.Subscription.tenant_id == tenant.id)
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    module_rows = (
        db.query(models.TenantModule)
        .filter(models.TenantModule.tenant_id == tenant.id)
        .all()
    )
    return SubscriptionOut(
        id=subscription.id,
        plan_id=subscription.plan_id,
        status=subscription.status.value,
        started_at=subscription.started_at,
        current_period_end=subscription.current_period_end,
        modules=[tm.module for tm in module_rows],
    )


class SubscriptionAssignPayload(BaseModel):
    plan_id: str


@router.post("/subscription", response_model=SubscriptionOut)
def assign_subscription(
    payload: SubscriptionAssignPayload,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    _: models.User = Depends(require_roles(models.UserRole.owner)),
):
    subscription = assign_plan_to_tenant(db, tenant.id, payload.plan_id)
    modules = db.query(models.TenantModule).filter(models.TenantModule.tenant_id == tenant.id).all()
    return SubscriptionOut(
        id=subscription.id,
        plan_id=subscription.plan_id,
        status=subscription.status.value,
        started_at=subscription.started_at,
        current_period_end=subscription.current_period_end,
        modules=[m.module for m in modules],
    )
