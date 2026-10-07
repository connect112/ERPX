"""certificate review: per-exam switch, per-person verified flag and name adjustment

Revision ID: 0062
Revises: 0061
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0062"
down_revision: Union[str, None] = "0061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workshop_exams", sa.Column("certificate_review", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("workshop_exam_attendees", sa.Column("certificate_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workshop_exam_attendees", sa.Column("certificate_adjust", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("workshop_exam_attendees", "certificate_adjust")
    op.drop_column("workshop_exam_attendees", "certificate_verified_at")
    op.drop_column("workshop_exams", "certificate_review")
