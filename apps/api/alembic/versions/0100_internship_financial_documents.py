"""internship onboarding: receipts, invoices and credit notes; refunds linked to their payment

Revision ID: 0100
Revises: 0099
Create Date: 2026-10-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0100"
down_revision: Union[str, None] = "0099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # counters get a series, so receipts and credit notes are numbered apart from application references
    op.add_column("internship_onboarding_counters", sa.Column("series", sa.String(20), nullable=False, server_default="application"))
    op.drop_constraint("uq_onboarding_counter", "internship_onboarding_counters", type_="unique")
    op.create_unique_constraint("uq_onboarding_counter_series", "internship_onboarding_counters", ["organization_id", "series", "year"])

    op.add_column("internship_payment_transactions", sa.Column(
        "refund_of_id", _UUID, sa.ForeignKey("internship_payment_transactions.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("internship_payment_transactions", sa.Column("provider_refund_id", sa.String(64), nullable=True))
    # Optional virus scanning (ClamAV, off by default): what was recorded for each upload.
    op.add_column("internship_onboarding_documents", sa.Column("scan_status", sa.String(20), nullable=False, server_default="not_scanned"))
    op.add_column("internship_payment_transactions", sa.Column("proof_scan_status", sa.String(20), nullable=True))
    # identity documents: the file is removed by a reviewer after the retention period; the row stays
    op.add_column("internship_onboarding_documents", sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("internship_onboarding_documents", sa.Column(
        "removed_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_internship_payment_transactions_refund_of_id", "internship_payment_transactions", ["refund_of_id"])

    op.create_table(
        "internship_financial_documents",
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", _UUID, sa.ForeignKey("internship_onboarding_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", _UUID, sa.ForeignKey("internship_payment_transactions.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=False),
        sa.Column("storage_key", sa.String(300), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email_status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("email_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "number", name="uq_financial_document_number"),
        sa.CheckConstraint("kind IN ('receipt', 'tax_invoice', 'credit_note')", name="ck_financial_document_kind"),
    )
    op.create_index("ix_internship_financial_documents_organization_id", "internship_financial_documents", ["organization_id"])
    op.create_index("ix_internship_financial_documents_application_id", "internship_financial_documents", ["application_id"])


def downgrade() -> None:
    op.drop_table("internship_financial_documents")
    op.drop_index("ix_internship_payment_transactions_refund_of_id", "internship_payment_transactions")
    op.drop_column("internship_payment_transactions", "proof_scan_status")
    op.drop_column("internship_onboarding_documents", "removed_by_user_id")
    op.drop_column("internship_onboarding_documents", "removed_at")
    op.drop_column("internship_onboarding_documents", "scan_status")
    op.drop_column("internship_payment_transactions", "provider_refund_id")
    op.drop_column("internship_payment_transactions", "refund_of_id")
    op.drop_constraint("uq_onboarding_counter_series", "internship_onboarding_counters", type_="unique")
    # rows of other series would collide with the old (organization, year) key; they only exist from 0100 on
    op.execute("DELETE FROM internship_onboarding_counters WHERE series <> 'application'")
    op.create_unique_constraint("uq_onboarding_counter", "internship_onboarding_counters", ["organization_id", "year"])
    op.drop_column("internship_onboarding_counters", "series")
