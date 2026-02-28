from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import require_module, require_roles
from app.db import get_db
from app.services.insights import get_insights
from app.tenancy import TenantContext

router = APIRouter(prefix="/admin/insights", tags=["insights"])


@router.get("", response_model=schemas.InsightsOut)
def get_insights_endpoint(
    start_date: str | None = Query(default=None, description="ISO date (YYYY-MM-DD)"),
    end_date: str | None = Query(default=None, description="ISO date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module("insights")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager)),
):
    return get_insights(db, tenant.id, start_date=start_date, end_date=end_date)
