"""create hackathons, teams, team members, submissions tables

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

hackathon_status_enum = postgresql.ENUM(
    "draft", "registration_open", "ongoing", "completed", "cancelled", name="hackathon_status"
)

_ALL_ENUMS = [hackathon_status_enum]


def _tc():
    return [
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "hackathons",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("theme", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("registration_deadline", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("max_team_size", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("prize_pool", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "status", postgresql.ENUM("draft", "registration_open", "ongoing", "completed", "cancelled", name="hackathon_status", create_type=False),
            nullable=False, server_default="draft",
        ),
        sa.UniqueConstraint("organization_id", "code", name="uq_hackathon_org_code"),
    )
    op.create_index("ix_hackathons_organization_id", "hackathons", ["organization_id"])
    op.create_index("ix_hackathons_status", "hackathons", ["status"])

    op.create_table(
        "hackathon_teams",
        *_tc(),
        sa.Column("hackathon_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("hackathon_id", "name", name="uq_hackathon_team_name"),
    )
    op.create_index("ix_hackathon_teams_hackathon_id", "hackathon_teams", ["hackathon_id"])
    op.create_index("ix_hackathon_teams_created_by_student_id", "hackathon_teams", ["created_by_student_id"])

    op.create_table(
        "hackathon_team_members",
        *_tc(),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hackathon_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("team_id", "student_id", name="uq_team_member_student"),
    )
    op.create_index("ix_hackathon_team_members_team_id", "hackathon_team_members", ["team_id"])
    op.create_index("ix_hackathon_team_members_student_id", "hackathon_team_members", ["student_id"])

    op.create_table(
        "hackathon_submissions",
        *_tc(),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hackathon_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("repo_url", sa.String(length=512), nullable=True),
        sa.Column("demo_url", sa.String(length=512), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.UniqueConstraint("team_id", name="uq_hackathon_submission_team"),
    )
    op.create_index("ix_hackathon_submissions_team_id", "hackathon_submissions", ["team_id"])


def downgrade() -> None:
    op.drop_table("hackathon_submissions")
    op.drop_table("hackathon_team_members")
    op.drop_table("hackathon_teams")
    op.drop_table("hackathons")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
