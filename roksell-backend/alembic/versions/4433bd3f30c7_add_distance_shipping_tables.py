"""add distance-based shipping tables

Revision ID: 4433bd3f30c7
Revises: 015452ad9d78
Create Date: 2025-10-24 21:33:23.084090

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4433bd3f30c7"
down_revision: Union[str, Sequence[str], None] = "015452ad9d78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shipping_distance_tiers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("km_min", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("km_max", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("km_min", "km_max", name="uq_shipping_distance_interval"),
    )
    op.create_table(
        "shipping_overrides",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("postal_code", sa.CHAR(length=8), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "geocode_cache",
        sa.Column("postal_code", sa.CHAR(length=8), nullable=False),
        sa.Column("lat", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("lon", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("postal_code"),
    )
    op.create_table(
        "stores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("lat", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("lon", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_table("shipping_zip_ranges")


def downgrade() -> None:
    op.create_table(
        "shipping_zip_ranges",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("zip_start", sa.CHAR(length=8), nullable=False),
        sa.Column("zip_end", sa.CHAR(length=8), nullable=False),
        sa.Column("amount_cents", sa.INTEGER(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("zip_start", "zip_end", name="uq_shipping_zip_range"),
    )
    op.drop_table("stores")
    op.drop_table("geocode_cache")
    op.drop_table("shipping_overrides")
    op.drop_table("shipping_distance_tiers")
