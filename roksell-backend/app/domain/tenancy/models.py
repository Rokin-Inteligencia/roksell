from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.domain.core.enums import TenantStatus, UserRole
from app.domain.customer.enums import CustomerPersonType


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    status: Mapped[TenantStatus] = mapped_column(Enum(TenantStatus), default=TenantStatus.active, nullable=False)
    timezone: Mapped[str] = mapped_column(String, default="America/Sao_Paulo", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="BRL", nullable=False)
    default_locale: Mapped[str] = mapped_column(String(5), default="pt-BR", nullable=False)
    users_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    stores_limit: Mapped[int | None] = mapped_column(Integer)
    person_type: Mapped[CustomerPersonType] = mapped_column(
        Enum(CustomerPersonType, name="customerpersontype"),
        default=CustomerPersonType.company,
        nullable=False,
    )
    document: Mapped[str | None] = mapped_column(String(32))
    legal_name: Mapped[str | None] = mapped_column(String)
    trade_name: Mapped[str | None] = mapped_column(String)
    state_registration: Mapped[str | None] = mapped_column(String(32))
    municipal_registration: Mapped[str | None] = mapped_column(String(32))
    contact_name: Mapped[str | None] = mapped_column(String)
    contact_email: Mapped[str | None] = mapped_column(String)
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    financial_contact_name: Mapped[str | None] = mapped_column(String)
    financial_contact_email: Mapped[str | None] = mapped_column(String)
    financial_contact_phone: Mapped[str | None] = mapped_column(String(32))
    billing_postal_code: Mapped[str | None] = mapped_column(String(16))
    billing_street: Mapped[str | None] = mapped_column(String)
    billing_number: Mapped[str | None] = mapped_column(String(32))
    billing_district: Mapped[str | None] = mapped_column(String)
    billing_city: Mapped[str | None] = mapped_column(String)
    billing_state: Mapped[str | None] = mapped_column(String(2))
    billing_complement: Mapped[str | None] = mapped_column(String)
    onboarding_origin: Mapped[str] = mapped_column(String(32), default="admin_manual", nullable=False)
    activation_mode: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    payment_provider: Mapped[str | None] = mapped_column(String(64))
    payment_reference: Mapped[str | None] = mapped_column(String(128))
    activation_notes: Mapped[str | None] = mapped_column(Text)
    signup_payload_json: Mapped[str | None] = mapped_column(Text)
    activated_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    payment_link_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payment_link_config: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TenantModule(Base):
    __tablename__ = "tenant_modules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module", name="uq_tenant_module"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserGroup(Base):
    __tablename__ = "user_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_user_group_name_tenant"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    permissions_json: Mapped[str | None] = mapped_column(Text)
    store_ids_json: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_email_tenant"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.owner, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_active_sessions: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    group_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("user_groups.id", ondelete="SET NULL"))
    default_store_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stores.id"))
    last_login_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(64))
