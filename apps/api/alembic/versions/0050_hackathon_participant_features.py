"""hackathon problem statements, team reports, leaderboard visibility

Revision ID: 0050
Revises: 0049
Create Date: 2026-10-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id_and_timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("hackathons", sa.Column("leaderboard_visible", sa.Boolean(), server_default="false", nullable=False))

    op.create_table(
        "hackathon_problem_statements",
        *_id_and_timestamps(),
        sa.Column("hackathon_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_hackathon_problem_statements_hackathon_id", "hackathon_problem_statements", ["hackathon_id"])

    op.add_column(
        "hackathon_teams",
        sa.Column(
            "problem_statement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hackathon_problem_statements.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        "hackathon_team_reports",
        *_id_and_timestamps(),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hackathon_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("uploaded_by_student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("team_id", name="uq_hackathon_team_report_team"),
    )
    op.create_index("ix_hackathon_team_reports_team_id", "hackathon_team_reports", ["team_id"])


def downgrade() -> None:
    op.drop_table("hackathon_team_reports")
    op.drop_column("hackathon_teams", "problem_statement_id")
    op.drop_table("hackathon_problem_statements")
    op.drop_column("hackathons", "leaderboard_visible")
