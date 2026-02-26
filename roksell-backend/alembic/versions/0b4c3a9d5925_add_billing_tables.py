"""add billing tables

Revision ID: 0b4c3a9d5925
Revises: 4e23b1664d6e
Create Date: 2025-11-15 14:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0b4c3a9d5925"
down_revision: Union[str, Sequence[str], None] = "4e23b1664d6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "modules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )

    op.create_table(
        "plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="BRL"),
        sa.Column(
            "interval",
            sa.Enum("monthly", "yearly", name="planinterval"),
            nullable=False,
            server_default="monthly",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "plan_modules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("module_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "module_id", name="uq_plan_module"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum("trialing", "active", "past_due", "canceled", "suspended", name="subscriptionstatus"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_table("plan_modules")
    op.drop_table("plans")
    op.drop_table("modules")
    sa.Enum(name="subscriptionstatus").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="planinterval").drop(op.get_bind(), checkfirst=False)
