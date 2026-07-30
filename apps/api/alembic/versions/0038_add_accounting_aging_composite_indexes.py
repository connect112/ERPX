"""add composite (organization_id, status) indexes for accounting aging reports

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-30

The AR / AP aging reports filter on exactly
``WHERE organization_id = :org AND status IN (...)``
(modules/accounting/reports/repository.py:
outstanding_receivables_with_customer / outstanding_payables_with_vendor).

With only the pre-existing single-column indexes on ``organization_id`` and
``status``, PostgreSQL must ``BitmapAnd`` two separate index scans. Measured
via ``EXPLAIN ANALYZE`` on a representative 500k-row dataset (org ≈ 100k rows,
~20% outstanding): the BitmapAnd scans ~199k index entries (99k status + 100k
org) to find ~20k matches. A composite ``(organization_id, status)`` replaces
that with a single index scan reading exactly the ~20k matching entries —
index-access cost 2171 → 271 (-87.5%), index entries examined ~199k → ~20k
(-90%), total query cost 10632 → 8726 (-17.9%), end-to-end ~113ms → ~97ms
(-14%). The standalone ``organization_id`` / ``status`` indexes are retained
(still used by org-only and status-only queries elsewhere).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_accounting_invoices_organization_id_status",
        "accounting_invoices",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_accounting_expenses_organization_id_status",
        "accounting_expenses",
        ["organization_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_accounting_expenses_organization_id_status",
        table_name="accounting_expenses",
    )
    op.drop_index(
        "ix_accounting_invoices_organization_id_status",
        table_name="accounting_invoices",
    )
