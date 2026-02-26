from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ProductMaster(Base):
    __tablename__ = "product_masters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name_canonical: Mapped[str] = mapped_column(String, nullable=False)
    sku_global: Mapped[str | None] = mapped_column(String(64), index=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    products = relationship("Product", back_populates="master")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "store_id", "name", name="uq_category_name_store_tenant"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    products = relationship("Product", back_populates="category")


class Additional(Base):
    __tablename__ = "additionals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "store_id", "name", name="uq_additional_name_store_tenant"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    product_links = relationship("ProductAdditional", back_populates="additional", cascade="all, delete-orphan")


class ProductAdditional(Base):
    __tablename__ = "product_additionals"

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    additional_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("additionals.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    product = relationship("Product", back_populates="additional_links")
    additional = relationship("Additional", back_populates="product_links")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_master_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_masters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    store_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("categories.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    additionals_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    block_sale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    availability_status: Mapped[str] = mapped_column(String(24), default="available", nullable=False)
    tags: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text)
    video_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    category = relationship("Category", back_populates="products")
    master = relationship("ProductMaster", back_populates="products")
    additional_links = relationship("ProductAdditional", back_populates="product", cascade="all, delete-orphan")

    @property
    def additional_ids(self) -> list[str]:
        return [link.additional_id for link in self.additional_links]
