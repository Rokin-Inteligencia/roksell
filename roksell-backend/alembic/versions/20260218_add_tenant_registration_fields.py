"""add tenant registration and activation fields

Revision ID: 20260218_add_tenant_registration_fields
Revises: 20260217_store_settings_shipping
Create Date: 2026-02-18 14:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260218_add_tenant_registration_fields"
down_revision = "20260217_store_settings_shipping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("legal_name", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("trade_name", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("state_registration", sa.String(length=32), nullable=True))
    op.add_column("tenants", sa.Column("municipal_registration", sa.String(length=32), nullable=True))
    op.add_column("tenants", sa.Column("contact_name", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("contact_email", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("contact_phone", sa.String(length=32), nullable=True))
    op.add_column("tenants", sa.Column("financial_contact_name", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("financial_contact_email", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("financial_contact_phone", sa.String(length=32), nullable=True))
    op.add_column("tenants", sa.Column("billing_postal_code", sa.String(length=16), nullable=True))
    op.add_column("tenants", sa.Column("billing_street", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("billing_number", sa.String(length=32), nullable=True))
    op.add_column("tenants", sa.Column("billing_district", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("billing_city", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("billing_state", sa.String(length=2), nullable=True))
    op.add_column("tenants", sa.Column("billing_complement", sa.String(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("onboarding_origin", sa.String(length=32), nullable=False, server_default="admin_manual"),
    )
    op.add_column(
        "tenants",
        sa.Column("activation_mode", sa.String(length=32), nullable=False, server_default="manual"),
    )
    op.add_column("tenants", sa.Column("payment_provider", sa.String(length=64), nullable=True))
    op.add_column("tenants", sa.Column("payment_reference", sa.String(length=128), nullable=True))
    op.add_column("tenants", sa.Column("activation_notes", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("signup_payload_json", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "activated_at")
    op.drop_column("tenants", "signup_payload_json")
    op.drop_column("tenants", "activation_notes")
    op.drop_column("tenants", "payment_reference")
    op.drop_column("tenants", "payment_provider")
    op.drop_column("tenants", "activation_mode")
    op.drop_column("tenants", "onboarding_origin")
    op.drop_column("tenants", "billing_complement")
    op.drop_column("tenants", "billing_state")
    op.drop_column("tenants", "billing_city")
    op.drop_column("tenants", "billing_district")
    op.drop_column("tenants", "billing_number")
    op.drop_column("tenants", "billing_street")
    op.drop_column("tenants", "billing_postal_code")
    op.drop_column("tenants", "financial_contact_phone")
    op.drop_column("tenants", "financial_contact_email")
    op.drop_column("tenants", "financial_contact_name")
    op.drop_column("tenants", "contact_phone")
    op.drop_column("tenants", "contact_email")
    op.drop_column("tenants", "contact_name")
    op.drop_column("tenants", "municipal_registration")
    op.drop_column("tenants", "state_registration")
    op.drop_column("tenants", "trade_name")
    op.drop_column("tenants", "legal_name")
