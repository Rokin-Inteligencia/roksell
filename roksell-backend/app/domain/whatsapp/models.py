from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WhatsAppMessageLog(Base):
    __tablename__ = "whatsapp_message_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE")
    )
    to_phone: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="sent")
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WhatsAppConversation(Base):
    __tablename__ = "whatsapp_conversations"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    phone: Mapped[str] = mapped_column(String, primary_key=True)
    profile_name: Mapped[str | None] = mapped_column(Text)
    last_inbound_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    last_read_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WhatsAppInboundMessage(Base):
    __tablename__ = "whatsapp_inbound_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_phone: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    message_type: Mapped[str | None] = mapped_column(String(32))
    message_text: Mapped[str | None] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(Text)
    media_mime: Mapped[str | None] = mapped_column(String(128))
    payload_json: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WhatsAppPushSubscription(Base):
    __tablename__ = "whatsapp_push_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    expiration_time: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
