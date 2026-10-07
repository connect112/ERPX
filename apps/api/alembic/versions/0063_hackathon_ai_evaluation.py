"""hackathon: automatic (AI) evaluation of submitted reports against the task's success criteria

Revision ID: 0063
Revises: 0062
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0063"
down_revision: Union[str, None] = "0062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hackathons", sa.Column("ai_evaluation_auto", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("hackathon_task_submissions", sa.Column("ai_evaluated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hackathon_task_submissions", sa.Column("ai_reasons", postgresql.JSONB(), nullable=True))
    op.add_column("hackathon_task_submissions", sa.Column("ai_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("hackathon_task_submissions", "ai_error")
    op.drop_column("hackathon_task_submissions", "ai_reasons")
    op.drop_column("hackathon_task_submissions", "ai_evaluated_at")
    op.drop_column("hackathons", "ai_evaluation_auto")
