from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain.billing.enums import PlanInterval, SubscriptionStatus


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="BRL", nullable=False)
    interval: Mapped[PlanInterval] = mapped_column(Enum(PlanInterval), default=PlanInterval.monthly, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    modules = relationship("PlanModule", cascade="all, delete-orphan", back_populates="plan")


class PlanModule(Base):
    __tablename__ = "plan_modules"
    __table_args__ = (
        UniqueConstraint("plan_id", "module_id", name="uq_plan_module"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    module_id: Mapped[str] = mapped_column(String(36), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False)
    plan = relationship("Plan", back_populates="modules")
    module = relationship("Module")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("plans.id"), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), nullable=False)
    started_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    current_period_end: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    cancel_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    trial_end_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[str | None] = mapped_column(Text)
    plan = relationship("Plan")
