"""Next sequential order code per tenant."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def get_next_order_code(db: Session, tenant_id: str) -> int:
    """Return next sequential code (1, 2, ...) for the tenant. Unique per tenant."""
    q = (
        db.query(func.coalesce(func.max(models.Order.code), 0))
        .filter(models.Order.tenant_id == tenant_id)
    )
    result = q.scalar()
    return (result or 0) + 1
