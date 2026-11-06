"""receipt designer: stored designs, their versions, uploaded images, and a guard that issued documents never change

Revision ID: 0103
Revises: 0101
Create Date: 2026-11-07

Additive only. Three new tables (designs, design versions, images) and one trigger. No existing row is read, rewritten or deleted;
internship_financial_documents (receipts, tax invoices, credit notes) keeps every column and every row exactly as it is.

- internship_receipt_designs: an organization's default design, an internship's own design, or a named reusable template.
  Presentation only (colours, sections, wording, which image); the issuer's legal details stay in the onboarding settings.
- internship_receipt_design_versions: every saved version, kept for good.
- internship_receipt_assets: uploaded logo / signature / stamp images, immutable (a replacement is a new row).
- A BEFORE UPDATE trigger on internship_financial_documents refuses any change to what makes a document what it is (number, kind,
  amount, currency, parties, details, stored file and its checksum, issue time). Only the email delivery fields can change, as
  before. A correction is a credit note, never an edit.

Revision order: this migration branches from 0101 so it does not depend on 0102 (pull request "onboarding: seven improvements").
Whichever of the two reaches master second must set its down_revision to the other's revision (one line); until then
`alembic heads` would list two heads. tests/unit/test_alembic_single_head.py fails if that is forgotten.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0103"
down_revision: Union[str, None] = "0101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)
_TS = sa.DateTime(timezone=True)

GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION internship_financial_documents_immutable() RETURNS trigger AS $$
BEGIN
  IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
     OR NEW.application_id IS DISTINCT FROM OLD.application_id
     OR NEW.transaction_id IS DISTINCT FROM OLD.transaction_id
     OR NEW.kind IS DISTINCT FROM OLD.kind
     OR NEW.number IS DISTINCT FROM OLD.number
     OR NEW.amount IS DISTINCT FROM OLD.amount
     OR NEW.currency IS DISTINCT FROM OLD.currency
     OR NEW.details IS DISTINCT FROM OLD.details
     OR NEW.storage_key IS DISTINCT FROM OLD.storage_key
     OR NEW.sha256 IS DISTINCT FROM OLD.sha256
     OR NEW.issued_at IS DISTINCT FROM OLD.issued_at
  THEN
    RAISE EXCEPTION 'An issued financial document cannot be changed (%). Correct it with a credit note.', OLD.number
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END
$$ LANGUAGE plpgsql
"""
GUARD_TRIGGER = """
CREATE TRIGGER trg_internship_financial_documents_immutable
BEFORE UPDATE ON internship_financial_documents
FOR EACH ROW EXECUTE FUNCTION internship_financial_documents_immutable()
"""


def _base(name: str, *columns: sa.Column, **kw):
    return op.create_table(
        name,
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        *columns,
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.func.now(), nullable=False),
        **kw,
    )


def upgrade() -> None:
    _base(
        "internship_receipt_designs",
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(12), nullable=False),
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("design", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("archived", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("updated_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint(
            "(scope = 'internship' AND internship_id IS NOT NULL) OR (scope IN ('organization', 'template') AND internship_id IS NULL)",
            name="ck_receipt_design_scope",
        ),
    )
    op.create_index("ix_internship_receipt_designs_organization_id", "internship_receipt_designs", ["organization_id"])
    op.create_index("uq_receipt_design_org", "internship_receipt_designs", ["organization_id"], unique=True, postgresql_where=sa.text("scope = 'organization'"))
    op.create_index("uq_receipt_design_internship", "internship_receipt_designs", ["internship_id"], unique=True, postgresql_where=sa.text("scope = 'internship'"))
    op.create_index("uq_receipt_design_template", "internship_receipt_designs", ["organization_id", "name"], unique=True, postgresql_where=sa.text("scope = 'template'"))

    _base(
        "internship_receipt_design_versions",
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("design_id", _UUID, sa.ForeignKey("internship_receipt_designs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("design", postgresql.JSONB(), nullable=False),
        sa.Column("created_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("design_id", "version", name="uq_receipt_design_version"),
    )
    op.create_index("ix_internship_receipt_design_versions_organization_id", "internship_receipt_design_versions", ["organization_id"])
    op.create_index("ix_internship_receipt_design_versions_design_id", "internship_receipt_design_versions", ["design_id"])

    _base(
        "internship_receipt_assets",
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("filename", sa.String(160), nullable=False),
        sa.Column("content_type", sa.String(30), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("uploaded_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("archived_at", _TS, nullable=True),
    )
    op.create_index("ix_internship_receipt_assets_organization_id", "internship_receipt_assets", ["organization_id"])
    op.create_index("ix_receipt_assets_org_kind", "internship_receipt_assets", ["organization_id", "kind"])

    op.execute(GUARD_FUNCTION)
    op.execute(GUARD_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_internship_financial_documents_immutable ON internship_financial_documents")
    op.execute("DROP FUNCTION IF EXISTS internship_financial_documents_immutable()")
    op.drop_table("internship_receipt_assets")
    op.drop_table("internship_receipt_design_versions")
    op.drop_table("internship_receipt_designs")
