"""placements job feed: years of experience a job asks for

Revision ID: 0066
Revises: 0065
Create Date: 2026-10-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0066"
down_revision: Union[str, None] = "0065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("placement_external_jobs", sa.Column("experience_min", sa.SmallInteger(), nullable=True))
    op.add_column("placement_external_jobs", sa.Column("experience_max", sa.SmallInteger(), nullable=True))
    op.add_column("placement_external_jobs", sa.Column("experience_estimated", sa.Boolean(), server_default="false", nullable=False))
    # Existing jobs are read for their experience by the next refresh (it doesn't need the job sites).
    op.add_column("placement_external_jobs", sa.Column("experience_parsed", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("placement_external_jobs", "experience_parsed")
    op.drop_column("placement_external_jobs", "experience_estimated")
    op.drop_column("placement_external_jobs", "experience_max")
    op.drop_column("placement_external_jobs", "experience_min")
