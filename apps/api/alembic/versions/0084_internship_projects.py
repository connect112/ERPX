"""internship projects: projects, student choices and submissions

Revision ID: 0084
Revises: 0083
Create Date: 2026-10-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0084"
down_revision: Union[str, None] = "0083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("draft", "published", "closed", name="internship_project_status").create(bind, checkfirst=True)
    postgresql.ENUM("file", "email", "repository", name="internship_submission_method").create(bind, checkfirst=True)

    op.create_table(
        "internship_projects",
        *_base(),
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objectives", sa.Text(), nullable=True),
        sa.Column("rules", sa.Text(), nullable=True),
        sa.Column("submission_instructions", sa.Text(), nullable=True),
        sa.Column("reference_links", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("allow_file", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("allow_email", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allow_repository", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("submission_email", sa.String(255), nullable=True),
        sa.Column("max_files", sa.Integer(), server_default="5", nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("allow_late", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", postgresql.ENUM(name="internship_project_status", create_type=False), server_default="draft", nullable=False),
    )
    for column in ("organization_id", "internship_id", "status"):
        op.create_index(f"ix_internship_projects_{column}", "internship_projects", [column])

    op.create_table(
        "internship_project_choices",
        *_base(),
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", _UUID, sa.ForeignKey("internship_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selection_id", _UUID, sa.ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chosen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("internship_id", "selection_id", name="uq_project_choice_student"),
    )
    for column in ("organization_id", "internship_id", "project_id", "selection_id"):
        op.create_index(f"ix_internship_project_choices_{column}", "internship_project_choices", [column])

    op.create_table(
        "internship_project_submissions",
        *_base(),
        sa.Column("project_id", _UUID, sa.ForeignKey("internship_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selection_id", _UUID, sa.ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", postgresql.ENUM(name="internship_submission_method", create_type=False), nullable=False),
        sa.Column("repository_url", sa.String(500), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_late", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("resubmission_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("project_id", "selection_id", name="uq_project_submission"),
    )
    for column in ("organization_id", "project_id", "selection_id"):
        op.create_index(f"ix_internship_project_submissions_{column}", "internship_project_submissions", [column])


def downgrade() -> None:
    op.drop_table("internship_project_submissions")
    op.drop_table("internship_project_choices")
    op.drop_table("internship_projects")
    postgresql.ENUM(name="internship_submission_method").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="internship_project_status").drop(op.get_bind(), checkfirst=True)
