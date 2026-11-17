"""internship LMS access: remember when the student already had the course enrolment

Revision ID: 0106
Revises: 0105
Create Date: 2026-11-17

Additive only: one boolean column on our_internship_selections, false for every existing row. No row is deleted and no enrolment, course,
student, payment or document is touched.

- lms_enrolment_preexisting: true when the student already had a live enrolment in the course at the moment LMS access was granted
  through the internship (they were enrolled some other way). Revoking that access then leaves the enrolment alone. Every access granted
  before this migration stays false, which is exactly how revoking has always behaved (it drops the enrolment); nothing is guessed about
  history. See ops/preflight/0104_0106_lms_access_ambiguity.sql for a read-only list of records worth reviewing.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0106"
down_revision: Union[str, None] = "0105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "our_internship_selections",
        sa.Column("lms_enrolment_preexisting", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("our_internship_selections", "lms_enrolment_preexisting")
