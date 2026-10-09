"""placements job feed: remember which jobs had their experience estimated by the AI

Revision ID: 0067
Revises: 0066
Create Date: 2026-10-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0067"
down_revision: Union[str, None] = "0066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("placement_external_jobs", sa.Column("experience_ai_done", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("placement_external_jobs", "experience_ai_done")
