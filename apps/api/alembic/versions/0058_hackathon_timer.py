"""hackathon timer: when the event starts and ends

Revision ID: 0058
Revises: 0057
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hackathons", sa.Column("timer_starts_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hackathons", sa.Column("timer_ends_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("hackathons", "timer_ends_at")
    op.drop_column("hackathons", "timer_starts_at")
