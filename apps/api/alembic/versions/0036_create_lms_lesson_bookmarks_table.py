"""create lms_lesson_bookmarks table

Revision ID: 0036
Revises: 0035
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lms_lesson_bookmarks",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("student_id", "lesson_id", name="uq_bookmark_student_lesson"),
    )
    op.create_index("ix_lms_lesson_bookmarks_student_id", "lms_lesson_bookmarks", ["student_id"])
    op.create_index("ix_lms_lesson_bookmarks_lesson_id", "lms_lesson_bookmarks", ["lesson_id"])


def downgrade() -> None:
    op.drop_table("lms_lesson_bookmarks")
