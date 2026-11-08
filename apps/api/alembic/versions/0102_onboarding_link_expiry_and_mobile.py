"""onboarding: the personal link expires an hour after completion; the student's confirmed mobile number

Revision ID: 0102
Revises: 0101
Create Date: 2026-11-07

Additive only: three nullable columns on internship_onboarding_applications. No row is deleted or rewritten, and no document, payment
order, receipt, ledger entry or student record is touched.

- link_expires_at: when the student's personal link stops working (one hour after onboarding was completed). Empty means the link has
  no expiry yet because onboarding is not complete.
- confirmed_phone / phone_changed_at: the mobile number the student confirmed in the portal, used for NEW payment orders, and when that
  number last changed (an order created before then carries the older number and is not reused).

Transition for students who are already complete: their links would otherwise expire the moment this release starts (they
completed more than an hour ago), including links in congratulation emails they have not opened yet. Each of them is given a
one-time 24 hours from this migration, then the same one-hour rule as everyone else applies. Applications that are not complete get
no value, so nothing expires while a student still has something to do.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0102"
down_revision: Union[str, None] = "0101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "internship_onboarding_applications"
# (kept as a constant so the tests can run exactly this statement)
BACKFILL_SQL = (
    f"UPDATE {_TABLE} SET link_expires_at = now() + interval '24 hours' "
    "WHERE completed_at IS NOT NULL AND cancelled_at IS NULL AND link_expires_at IS NULL"
)


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("link_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(_TABLE, sa.Column("confirmed_phone", sa.String(15), nullable=True))
    op.add_column(_TABLE, sa.Column("phone_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text(BACKFILL_SQL))


def downgrade() -> None:
    for column in ("phone_changed_at", "confirmed_phone", "link_expires_at"):
        op.drop_column(_TABLE, column)
