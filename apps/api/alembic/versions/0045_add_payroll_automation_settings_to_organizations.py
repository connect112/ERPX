"""add payroll automation settings to organizations

Revision ID: 0045
Revises: 0044
Create Date: 2026-09-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both nullable and both opt-in -- an org that leaves these unset keeps
    # today's behavior exactly (a generated payroll draft waits for an admin
    # to finalize it by hand). Setting both turns on the automatic
    # generate -> apply approved expenses -> finalize -> email pipeline.
    op.add_column(
        "organizations",
        sa.Column(
            "default_salary_payable_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounting_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "default_expense_reimbursement_component_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payroll_salary_components.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "default_expense_reimbursement_component_id")
    op.drop_column("organizations", "default_salary_payable_account_id")
