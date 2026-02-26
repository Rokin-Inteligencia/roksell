from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OperationsConfig(Base):
    __tablename__ = "operations_config"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    sla_minutes: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    delivery_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cover_image_url: Mapped[str | None] = mapped_column(Text)
    whatsapp_contact_phone: Mapped[str | None] = mapped_column(Text)
    whatsapp_order_message: Mapped[str | None] = mapped_column(Text)
    whatsapp_status_message: Mapped[str | None] = mapped_column(Text)
    whatsapp_last_read_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    pix_key: Mapped[str | None] = mapped_column(Text)
    whatsapp_enabled: Mapped[bool | None] = mapped_column(Boolean)
    whatsapp_token: Mapped[str | None] = mapped_column(Text)
    whatsapp_phone_number_id: Mapped[str | None] = mapped_column(Text)
    telegram_enabled: Mapped[bool | None] = mapped_column(Boolean)
    telegram_bot_token: Mapped[str | None] = mapped_column(Text)
    telegram_chat_id: Mapped[str | None] = mapped_column(Text)
    order_statuses: Mapped[str | None] = mapped_column(Text)
    order_status_canceled_color: Mapped[str | None] = mapped_column(Text)
    order_status_colors: Mapped[str | None] = mapped_column(Text)
    order_final_statuses: Mapped[str | None] = mapped_column(Text)
    operating_hours: Mapped[str | None] = mapped_column(Text)
    payment_methods: Mapped[str | None] = mapped_column(Text)
    shipping_method: Mapped[str | None] = mapped_column(Text)


class BlockedDay(Base):
    __tablename__ = "blocked_days"

    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    date: Mapped["Date"] = mapped_column(Date, primary_key=True)
    reason: Mapped[str | None] = mapped_column(Text)
