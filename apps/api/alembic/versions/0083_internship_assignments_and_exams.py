"""internship learning: exams can belong to an internship; assignments, submissions and stored files

Revision ID: 0083
Revises: 0082
Create Date: 2026-10-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0083"
down_revision: Union[str, None] = "0082"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _id_and_timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    # A workshop exam can belong to an internship (nullable: nothing existing is touched; deleting the internship keeps the exam).
    op.add_column(
        "workshop_exams",
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_workshop_exams_internship_id", "workshop_exams", ["internship_id"])

    op.create_table(
        "internship_files",
        *_id_and_timestamps(),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_type", sa.String(40), nullable=False),
        sa.Column("owner_id", _UUID, nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(600), nullable=False),
        sa.Column("uploaded_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_internship_files_organization_id", "internship_files", ["organization_id"])
    op.create_index("ix_internship_files_internship_id", "internship_files", ["internship_id"])
    op.create_index("ix_internship_files_owner_id", "internship_files", ["owner_id"])

    postgresql.ENUM("draft", "published", "closed", name="internship_assignment_status").create(
        op.get_bind(), checkfirst=True
    )
    op.create_table(
        "internship_assignments",
        *_id_and_timestamps(),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tasks", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("max_marks", sa.Integer(), server_default="100", nullable=False),
        sa.Column("rubric", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("allow_late", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("max_files", sa.Integer(), server_default="5", nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="internship_assignment_status", create_type=False),
            server_default="draft",
            nullable=False,
        ),
    )
    op.create_index("ix_internship_assignments_organization_id", "internship_assignments", ["organization_id"])
    op.create_index("ix_internship_assignments_internship_id", "internship_assignments", ["internship_id"])
    op.create_index("ix_internship_assignments_status", "internship_assignments", ["status"])

    op.create_table(
        "internship_assignment_submissions",
        *_id_and_timestamps(),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assignment_id", _UUID, sa.ForeignKey("internship_assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selection_id", _UUID, sa.ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_late", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("resubmission_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rubric_scores", postgresql.JSONB(), nullable=True),
        sa.Column("score", sa.Numeric(7, 2), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("assignment_id", "selection_id", name="uq_assignment_submission"),
    )
    op.create_index("ix_internship_assignment_submissions_organization_id", "internship_assignment_submissions", ["organization_id"])
    op.create_index("ix_internship_assignment_submissions_assignment_id", "internship_assignment_submissions", ["assignment_id"])
    op.create_index("ix_internship_assignment_submissions_selection_id", "internship_assignment_submissions", ["selection_id"])


def downgrade() -> None:
    op.drop_table("internship_assignment_submissions")
    op.drop_table("internship_assignments")
    postgresql.ENUM(name="internship_assignment_status").drop(op.get_bind(), checkfirst=True)
    op.drop_table("internship_files")
    op.drop_index("ix_workshop_exams_internship_id", table_name="workshop_exams")
    op.drop_column("workshop_exams", "internship_id")
