from sqlalchemy import Boolean, CHAR, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_customer_phone_tenant"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    origin_store_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stores.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    birthday: Mapped["Date | None"] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    postal_code: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    street: Mapped[str] = mapped_column(Text, nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    complement: Mapped[str | None] = mapped_column(Text)
    district: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    reference: Mapped[str | None] = mapped_column(Text)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
