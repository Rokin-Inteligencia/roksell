"""add customer plans and payment link fields

Revision ID: 20260210_add_customer_plans_and_payment_links
Revises: 20260208_add_product_availability_status
Create Date: 2026-02-10 10:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260210_add_customer_plans_and_payment_links"
down_revision = "20260208_add_product_availability_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    customer_person_enum = sa.Enum("individual", "company", name="customerpersontype")
    customer_person_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "customer_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("permissions_json", sa.Text(), nullable=True),
        sa.Column("settings_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_customer_plan_tenant_name"),
    )
    op.create_index("ix_customer_plans_tenant_id", "customer_plans", ["tenant_id"])

    op.add_column(
        "customers",
        sa.Column(
            "person_type",
            customer_person_enum,
            nullable=False,
            server_default="individual",
        ),
    )
    op.add_column("customers", sa.Column("document", sa.String(length=32), nullable=True))
    op.add_column(
        "customers",
        sa.Column("payment_link_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("customers", sa.Column("payment_link_config", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("customer_plan_id", sa.String(length=36), nullable=True))
    op.create_index("ix_customers_customer_plan_id", "customers", ["customer_plan_id"])
    op.create_foreign_key(
        "fk_customers_customer_plan_id",
        "customers",
        "customer_plans",
        ["customer_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_customers_customer_plan_id", "customers", type_="foreignkey")
    op.drop_index("ix_customers_customer_plan_id", table_name="customers")
    op.drop_column("customers", "customer_plan_id")
    op.drop_column("customers", "payment_link_config")
    op.drop_column("customers", "payment_link_enabled")
    op.drop_column("customers", "document")
    op.drop_column("customers", "person_type")

    op.drop_index("ix_customer_plans_tenant_id", table_name="customer_plans")
    op.drop_table("customer_plans")
    sa.Enum("individual", "company", name="customerpersontype").drop(op.get_bind(), checkfirst=False)
