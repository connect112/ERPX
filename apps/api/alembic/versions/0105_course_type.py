"""courses: a type (regular or internship) and whether an internship course shows the internship's fee

Revision ID: 0105
Revises: 0104
Create Date: 2026-11-10

Additive only. Two columns on courses; no course, chapter, lesson, resource, batch, enrolment or internship row is rewritten.

- course_type: 'regular' (the default; every existing course keeps its behaviour, price and links) or 'internship'. Existing
  courses that internships already use stay 'regular': they keep working exactly as before, and an administrator can turn one into
  an internship course from the course's edit screen.
- show_internship_fee: for an internship course, whether course screens show the linked internship's fee (read from its onboarding
  settings, to people allowed to see finance). False for every existing course.

Downgrade drops both columns and the enum type.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0105"
down_revision: Union[str, None] = "0104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

course_type = postgresql.ENUM("regular", "internship", name="course_type", create_type=False)


def upgrade() -> None:
    postgresql.ENUM("regular", "internship", name="course_type").create(op.get_bind(), checkfirst=True)
    op.add_column("courses", sa.Column("course_type", course_type, nullable=False, server_default="regular"))
    op.add_column("courses", sa.Column("show_internship_fee", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_courses_course_type", "courses", ["course_type"])


def downgrade() -> None:
    op.drop_index("ix_courses_course_type", table_name="courses")
    op.drop_column("courses", "show_internship_fee")
    op.drop_column("courses", "course_type")
    postgresql.ENUM(name="course_type").drop(op.get_bind(), checkfirst=True)
