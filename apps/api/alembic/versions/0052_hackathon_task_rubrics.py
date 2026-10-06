"""hackathon task marks, sub-tasks and rubric; rubric scores on submissions

Revision ID: 0052
Revises: 0051
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hackathon_problem_statements", sa.Column("marks", sa.Integer(), server_default="0", nullable=False))
    op.add_column(
        "hackathon_problem_statements",
        sa.Column("sub_tasks", postgresql.JSONB(), server_default="[]", nullable=False),
    )
    op.add_column(
        "hackathon_problem_statements",
        sa.Column("rubric", postgresql.JSONB(), server_default="[]", nullable=False),
    )
    # The description is now optional (the admin form shows it behind a toggle).
    op.alter_column("hackathon_problem_statements", "description", existing_type=sa.Text(), nullable=True)
    op.add_column("hackathon_task_submissions", sa.Column("rubric_scores", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("hackathon_task_submissions", "rubric_scores")
    op.execute("UPDATE hackathon_problem_statements SET description = '' WHERE description IS NULL")
    op.alter_column("hackathon_problem_statements", "description", existing_type=sa.Text(), nullable=False)
    op.drop_column("hackathon_problem_statements", "rubric")
    op.drop_column("hackathon_problem_statements", "sub_tasks")
    op.drop_column("hackathon_problem_statements", "marks")
