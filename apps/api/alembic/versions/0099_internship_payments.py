"""internship onboarding payments: orders, the ledger, gateway notifications

Revision ID: 0099
Revises: 0098
Create Date: 2026-10-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0099"
down_revision: Union[str, None] = "0098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _base(org_nullable: bool = False) -> list:
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "organization_id", _UUID,
            sa.ForeignKey("organizations.id", ondelete="SET NULL" if org_nullable else "CASCADE"), nullable=org_nullable,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "internship_payment_orders",
        *_base(),
        sa.Column("application_id", _UUID, sa.ForeignKey("internship_onboarding_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("merchant_order_id", sa.String(64), nullable=False, unique=True),
        sa.Column("provider", sa.String(20), nullable=True),
        sa.Column("provider_order_id", sa.String(64), nullable=True),
        sa.Column("payment_session_id", sa.String(300), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_payment_order_amount_positive"),
    )
    op.create_table(
        "internship_payment_transactions",
        *_base(),
        sa.Column("application_id", _UUID, sa.ForeignKey("internship_onboarding_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", _UUID, sa.ForeignKey("internship_payment_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("method", sa.String(20), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(25), nullable=False),
        sa.Column("provider", sa.String(20), nullable=True),
        sa.Column("provider_payment_id", sa.String(64), nullable=True),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("reference_normalized", sa.String(120), nullable=True),
        sa.Column("paid_on", sa.Date, nullable=True),
        sa.Column("proof_storage_key", sa.String(300), nullable=True),
        sa.Column("proof_filename", sa.String(160), nullable=True),
        sa.Column("proof_content_type", sa.String(60), nullable=True),
        sa.Column("proof_sha256", sa.String(64), nullable=True),
        sa.Column("remarks", sa.Text, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("verified_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_payment_transaction_amount_positive"),
        sa.CheckConstraint("kind IN ('payment', 'refund', 'charge', 'waiver')", name="ck_payment_transaction_kind"),
    )
    op.create_index(
        "uq_payment_reference_live", "internship_payment_transactions", ["organization_id", "reference_normalized"], unique=True,
        postgresql_where=sa.text("kind = 'payment' AND reference_normalized IS NOT NULL AND status IN ('awaiting_verification', 'confirmed')"),
    )
    op.create_index(
        "uq_payment_provider_payment", "internship_payment_transactions", ["provider", "provider_payment_id"], unique=True,
        postgresql_where=sa.text("provider_payment_id IS NOT NULL"),
    )
    op.create_table(
        "internship_payment_webhooks",
        *_base(org_nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("signature_valid", sa.Boolean, nullable=False),
        sa.Column("event_type", sa.String(60), nullable=True),
        sa.Column("merchant_order_id", sa.String(64), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(200), nullable=True),
    )
    for table, cols in (
        ("internship_payment_orders", ["organization_id", "application_id", "status"]),
        ("internship_payment_transactions", ["organization_id", "application_id", "order_id", "status"]),
        ("internship_payment_webhooks", ["organization_id", "merchant_order_id"]),
    ):
        for col in cols:
            op.create_index(f"ix_{table}_{col}", table, [col])


def downgrade() -> None:
    for table in ("internship_payment_webhooks", "internship_payment_transactions", "internship_payment_orders"):
        op.drop_table(table)
