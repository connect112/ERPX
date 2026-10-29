"""pentrix payments: a synchronised copy of every payment, and the daily reconciliation summaries

Revision ID: 0093
Revises: 0092
Create Date: 2026-10-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0093"
down_revision: Union[str, None] = "0092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _base(*extra):
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *extra,
    ]


def upgrade() -> None:
    op.create_table(
        "pentrix_payments",
        *_base(
            sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("pentrix_payment_id", sa.String(36), nullable=False),
            sa.Column("pentrix_user_id", sa.String(36), nullable=False),
            sa.Column("candidate_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("candidate_email", sa.String(255), nullable=False, server_default=""),
            sa.Column("provider", sa.String(20), nullable=False, server_default=""),
            sa.Column("provider_order_id", sa.String(128)),
            sa.Column("provider_payment_id", sa.String(128)),
            sa.Column("reference", sa.String(128)),
            sa.Column("purpose", sa.String(40), nullable=False, server_default=""),
            sa.Column("status", sa.String(24), nullable=False),
            sa.Column("amount_paise", sa.BigInteger, nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
            sa.Column("invoice_number", sa.String(64)),
            sa.Column("receipt_number", sa.String(64)),
            sa.Column("provisioning_status", sa.String(16)),
            sa.Column("created_at_source", sa.DateTime(timezone=True)),
            sa.Column("paid_at", sa.DateTime(timezone=True)),
            sa.Column("failed_at", sa.DateTime(timezone=True)),
            sa.Column("refunded_at", sa.DateTime(timezone=True)),
            sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        ),
    )
    op.create_unique_constraint("uq_pentrix_payments_pentrix_payment_id", "pentrix_payments", ["pentrix_payment_id"])
    op.create_index("ix_pentrix_payments_organization_id", "pentrix_payments", ["organization_id"])
    op.create_index("ix_pentrix_payments_pentrix_user_id", "pentrix_payments", ["pentrix_user_id"])
    op.create_index("ix_pentrix_payments_provider_payment_id", "pentrix_payments", ["provider_payment_id"])
    op.create_index("ix_pentrix_payments_invoice_number", "pentrix_payments", ["invoice_number"])
    op.create_index("ix_pentrix_payments_org_paid", "pentrix_payments", ["organization_id", "paid_at"])
    op.create_index("ix_pentrix_payments_org_status", "pentrix_payments", ["organization_id", "status"])
    op.create_index("ix_pentrix_payments_org_created", "pentrix_payments", ["organization_id", "created_at_source"])

    op.create_table(
        "pentrix_daily_summaries",
        *_base(
            sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("day", sa.Date, nullable=False),
            sa.Column("status", sa.String(10), nullable=False),
            sa.Column("successful_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("collected_paise", sa.BigInteger, nullable=False, server_default="0"),
            sa.Column("pending_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("refund_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("refunded_paise", sa.BigInteger, nullable=False, server_default="0"),
            sa.Column("partial_refund_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("pentrix_totals", postgresql.JSONB),
            sa.Column("mismatches", postgresql.JSONB),
            sa.Column("repaired_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
            sa.Column("last_error", sa.String(500)),
            sa.Column("reconciled_at", sa.DateTime(timezone=True)),
        ),
    )
    op.create_unique_constraint("uq_pentrix_daily_summary_day", "pentrix_daily_summaries", ["organization_id", "day"])
    op.create_index("ix_pentrix_daily_summaries_organization_id", "pentrix_daily_summaries", ["organization_id"])


def downgrade() -> None:
    op.drop_table("pentrix_daily_summaries")
    op.drop_table("pentrix_payments")
