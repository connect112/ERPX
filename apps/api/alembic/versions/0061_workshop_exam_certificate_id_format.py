"""customisable certificate ID format per workshop exam

Revision ID: 0061
Revises: 0060
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0061"
down_revision: Union[str, None] = "0060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workshop_exams", sa.Column("certificate_id_pattern", sa.String(80), nullable=True))
    op.add_column("workshop_exams", sa.Column("certificate_id_start", sa.Integer(), server_default="1", nullable=False))
    op.add_column("workshop_exams", sa.Column("certificate_id_counter", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("workshop_exams", "certificate_id_counter")
    op.drop_column("workshop_exams", "certificate_id_start")
    op.drop_column("workshop_exams", "certificate_id_pattern")
