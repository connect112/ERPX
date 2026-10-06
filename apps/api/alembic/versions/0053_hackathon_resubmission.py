"""hackathon resubmission settings; resubmission count and review time on task submissions

Revision ID: 0053
Revises: 0052
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hackathons", sa.Column("resubmission_enabled", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("hackathons", sa.Column("max_resubmissions", sa.Integer(), server_default="2", nullable=False))
    op.add_column(
        "hackathon_task_submissions", sa.Column("resubmission_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("hackathon_task_submissions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    # Submissions that already have a score count as reviewed.
    op.execute("UPDATE hackathon_task_submissions SET reviewed_at = submitted_at WHERE score IS NOT NULL")


def downgrade() -> None:
    op.drop_column("hackathon_task_submissions", "reviewed_at")
    op.drop_column("hackathon_task_submissions", "resubmission_count")
    op.drop_column("hackathons", "max_resubmissions")
    op.drop_column("hackathons", "resubmission_enabled")
