from sqlalchemy import Boolean, CHAR, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_store_slug_tenant"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    lat: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    lon: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(CHAR(8))
    street: Mapped[str | None] = mapped_column(String)
    number: Mapped[str | None] = mapped_column(String)
    district: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String(2))
    complement: Mapped[str | None] = mapped_column(String)
    reference: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String)
    sla_minutes: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    cover_image_url: Mapped[str | None] = mapped_column(Text)
    whatsapp_contact_phone: Mapped[str | None] = mapped_column(Text)
    payment_methods: Mapped[str | None] = mapped_column(Text)
    order_statuses: Mapped[str | None] = mapped_column(Text)
    order_status_canceled_color: Mapped[str | None] = mapped_column(Text)
    order_status_colors: Mapped[str | None] = mapped_column(Text)
    order_final_statuses: Mapped[str | None] = mapped_column(Text)
    shipping_method: Mapped[str | None] = mapped_column(Text)
    shipping_fixed_fee_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    closed_dates: Mapped[str | None] = mapped_column(Text)
    operating_hours: Mapped[str | None] = mapped_column(Text)
    allow_preorder_when_closed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Sao_Paulo")
    is_delivery: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StoreInventory(Base):
    __tablename__ = "store_inventory"
    __table_args__ = (
        UniqueConstraint("tenant_id", "store_id", "product_id", name="uq_inventory_store_product"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class GeocodeCache(Base):
    __tablename__ = "geocode_cache"

    postal_code: Mapped[str] = mapped_column(CHAR(8), primary_key=True)
    lat: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    lon: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ShippingDistanceTier(Base):
    __tablename__ = "shipping_distance_tiers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "store_id", "km_min", "km_max", name="uq_shipping_distance_interval"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    km_min: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    km_max: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)


class ShippingOverride(Base):
    __tablename__ = "shipping_overrides"
    __table_args__ = (
        UniqueConstraint("tenant_id", "postal_code", name="uq_shipping_override_postal_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    postal_code: Mapped[str | None] = mapped_column(CHAR(8))
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
