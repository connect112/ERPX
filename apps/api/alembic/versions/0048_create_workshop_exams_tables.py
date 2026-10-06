"""create workshop exam tables

Revision ID: 0048
Revises: 0047
Create Date: 2026-10-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id_and_timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    status_enum = postgresql.ENUM("draft", "open", "closed", name="workshop_exam_status", create_type=False)
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "workshop_exams",
        *_id_and_timestamps(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("status", status_enum, server_default="draft", nullable=False),
        sa.Column("show_result", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("public_code", sa.String(32), nullable=False),
        sa.Column("info_fields", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("certificate_release_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certificates_dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certificate_heading", sa.String(255), server_default="Certificate of Participation", nullable=False),
        sa.Column("certificate_text", sa.Text(), nullable=True),
    )
    op.create_index("ix_workshop_exams_organization_id", "workshop_exams", ["organization_id"])
    op.create_index("ix_workshop_exams_workshop_id", "workshop_exams", ["workshop_id"])
    op.create_index("ix_workshop_exams_status", "workshop_exams", ["status"])
    op.create_index("ix_workshop_exams_public_code", "workshop_exams", ["public_code"], unique=True)

    op.create_table(
        "workshop_exam_questions",
        *_id_and_timestamps(),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshop_exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("correct_indices", postgresql.JSONB(), nullable=False),
        sa.Column("allow_multiple", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("marks", sa.Integer(), server_default="1", nullable=False),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_workshop_exam_questions_exam_id", "workshop_exam_questions", ["exam_id"])

    op.create_table(
        "workshop_exam_attendees",
        *_id_and_timestamps(),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshop_exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("access_token", sa.String(64), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("info", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("answers", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("total_marks", sa.Integer(), nullable=True),
        sa.Column("certificate_number", sa.String(50), nullable=True),
        sa.Column("certificate_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("exam_id", "email", name="uq_workshop_exam_attendee_email"),
    )
    op.create_index("ix_workshop_exam_attendees_exam_id", "workshop_exam_attendees", ["exam_id"])
    op.create_index("ix_workshop_exam_attendees_access_token", "workshop_exam_attendees", ["access_token"], unique=True)
    op.create_index("ix_workshop_exam_attendees_certificate_number", "workshop_exam_attendees", ["certificate_number"], unique=True)


def downgrade() -> None:
    op.drop_table("workshop_exam_attendees")
    op.drop_table("workshop_exam_questions")
    op.drop_table("workshop_exams")
    postgresql.ENUM(name="workshop_exam_status").drop(op.get_bind(), checkfirst=True)
