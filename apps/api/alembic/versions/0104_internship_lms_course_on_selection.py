"""internship LMS access: remember which course a student was given access to

Revision ID: 0104
Revises: 0103
Create Date: 2026-11-10

Additive only: one nullable column on our_internship_selections. No row is deleted, no enrolment is changed, and no course, student,
payment or document is touched.

- lms_course_id: the course the student was enrolled in when LMS access was granted. Revoking access drops THAT enrolment, even if the
  internship has been linked to a different course since (before this column, revoking looked at the internship's current course).

Backfill: for students who already have (or had) LMS access, the column is set to the internship's current course, the only course
their access could have come from until now. Students without LMS access stay empty. The backfill is idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0104"
down_revision: Union[str, None] = "0103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKFILL_SQL = (
    "UPDATE our_internship_selections s SET lms_course_id = i.lms_course_id "
    "FROM our_internships i "
    "WHERE s.internship_id = i.id AND s.lms_status IN ('granted', 'revoked') "
    "AND s.lms_course_id IS NULL AND i.lms_course_id IS NOT NULL"
)


def upgrade() -> None:
    op.add_column(
        "our_internship_selections",
        sa.Column("lms_course_id", sa.UUID(), sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_our_internship_selections_lms_course_id", "our_internship_selections", ["lms_course_id"])
    op.execute(BACKFILL_SQL)


def downgrade() -> None:
    op.drop_index("ix_our_internship_selections_lms_course_id", table_name="our_internship_selections")
    op.drop_column("our_internship_selections", "lms_course_id")
