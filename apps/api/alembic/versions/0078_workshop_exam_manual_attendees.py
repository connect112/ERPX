"""workshop exams: students added by hand, and certificates sent without the exam

Revision ID: 0078
Revises: 0077
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0078"
down_revision: Union[str, None] = "0077"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workshop_exam_attendees", sa.Column("added_manually", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column(
        "workshop_exam_attendees", sa.Column("certificate_forced", sa.Boolean(), server_default="false", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("workshop_exam_attendees", "certificate_forced")
    op.drop_column("workshop_exam_attendees", "added_manually")
