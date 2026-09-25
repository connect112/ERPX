"""add week_off_days to organizations

Revision ID: 0043
Revises: 0042
Create Date: 2026-09-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Which weekdays (Python's date.weekday(): Monday=0..Sunday=6) count as
    # a paid weekly off for this org, even on days with no attendance
    # record at all. Server default '{6}' (Sunday only) matches the
    # behavior every existing org already had before this was configurable.
    op.add_column(
        "organizations",
        sa.Column(
            "week_off_days",
            ARRAY(sa.Integer()),
            nullable=False,
            server_default="{6}",
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "week_off_days")
