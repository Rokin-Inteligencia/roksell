from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.domain.core.enums import CampaignType


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        Index("ix_campaigns_tenant_coupon", "tenant_id", "coupon_code"),
        Index("ix_campaigns_tenant_active", "tenant_id", "is_active", "starts_at", "ends_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[CampaignType] = mapped_column(Enum(CampaignType), nullable=False)
    value_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    coupon_code: Mapped[str | None] = mapped_column(String(64))
    category_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("categories.id", ondelete="SET NULL"))
    min_order_cents: Mapped[int | None] = mapped_column(Integer)
    starts_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    banner_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    banner_position: Mapped[str | None] = mapped_column(String(16))
    banner_popup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    banner_image_url: Mapped[str | None] = mapped_column(Text)
    banner_link_url: Mapped[str | None] = mapped_column(Text)
    rule_config: Mapped[str | None] = mapped_column(Text)
    apply_mode: Mapped[str] = mapped_column(String(16), default="first", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CampaignStore(Base):
    __tablename__ = "campaign_stores"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    store_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True
    )
