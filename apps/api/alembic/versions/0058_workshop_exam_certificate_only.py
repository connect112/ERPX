"""certificate-only exam attendees (e.g. hackathon participants)

Revision ID: 0058
Revises: 0057
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workshop_exam_attendees",
        sa.Column("certificate_only", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("workshop_exam_attendees", "certificate_only")
