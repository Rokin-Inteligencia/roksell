from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.domain.core.enums import DeliveryStatus, PaymentMethod, PaymentStatus


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False)
    address_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customer_addresses.id"))
    store_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stores.id"))
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    shipping_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("campaigns.id"))
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_date: Mapped["Date | None"] = mapped_column(Date)
    channel: Mapped[str] = mapped_column(String, default="web", nullable=False)
    status: Mapped[str] = mapped_column(Text, default="received", nullable=False)
    delivery_window_start: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    delivery_window_end: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    txid: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[DeliveryStatus] = mapped_column(Enum(DeliveryStatus), default=DeliveryStatus.pending, nullable=False)
    distance_km: Mapped[Numeric | None] = mapped_column(Numeric(8, 2))
    eta: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    departed_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    proof_url: Mapped[str | None] = mapped_column(Text)
