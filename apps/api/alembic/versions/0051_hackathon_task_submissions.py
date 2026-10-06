"""hackathon per-task submissions; leaderboard visible by default

Revision ID: 0051
Revises: 0050
Create Date: 2026-10-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hackathon_task_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hackathon_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "problem_statement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hackathon_problem_statements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repo_url", sa.String(512), nullable=True),
        sa.Column("report_filename", sa.String(255), nullable=True),
        sa.Column("report_content_type", sa.String(100), nullable=True),
        sa.Column("report_size_bytes", sa.Integer(), nullable=True),
        sa.Column("report_data", sa.LargeBinary(), nullable=True),
        sa.Column("submitted_by_student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.UniqueConstraint("team_id", "problem_statement_id", name="uq_hackathon_task_submission"),
    )
    op.create_index("ix_hackathon_task_submissions_team_id", "hackathon_task_submissions", ["team_id"])
    op.create_index("ix_hackathon_task_submissions_problem_statement_id", "hackathon_task_submissions", ["problem_statement_id"])

    # The leaderboard now updates live as tasks are scored, so it is shown by default.
    op.alter_column("hackathons", "leaderboard_visible", server_default="true")
    op.execute("UPDATE hackathons SET leaderboard_visible = true")

    # Carry over what teams already did under the one-submission-per-team design:
    # their report, repository URL and score move onto the task they had chosen.
    op.execute(
        """
        INSERT INTO hackathon_task_submissions
            (team_id, problem_statement_id, repo_url, report_filename, report_content_type, report_size_bytes,
             report_data, submitted_by_student_id, submitted_at, score, feedback)
        SELECT t.id, t.problem_statement_id, s.repo_url, r.filename, r.content_type, r.size_bytes, r.data,
               r.uploaded_by_student_id, COALESCE(s.submitted_at, r.created_at, now()), s.score, s.feedback
        FROM hackathon_teams t
        LEFT JOIN hackathon_submissions s ON s.team_id = t.id
        LEFT JOIN hackathon_team_reports r ON r.team_id = t.id
        WHERE t.problem_statement_id IS NOT NULL AND (s.id IS NOT NULL OR r.id IS NOT NULL)
        """
    )


def downgrade() -> None:
    op.alter_column("hackathons", "leaderboard_visible", server_default="false")
    op.drop_table("hackathon_task_submissions")
