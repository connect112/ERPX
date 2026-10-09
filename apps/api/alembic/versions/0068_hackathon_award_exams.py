"""hackathon winner certificates: each award (1st, 2nd, 3rd place, participation) is a certificate exam of the hackathon

Revision ID: 0068
Revises: 0067
Create Date: 2026-10-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0068"
down_revision: Union[str, None] = "0067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workshop_exams",
        sa.Column("hackathon_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=True),
    )
    op.add_column("workshop_exams", sa.Column("award", sa.String(20), nullable=True))
    op.create_index("ix_workshop_exams_hackathon_id", "workshop_exams", ["hackathon_id"])
    op.create_index(
        "uq_workshop_exams_hackathon_award",
        "workshop_exams",
        ["hackathon_id", "award"],
        unique=True,
        postgresql_where=sa.text("hackathon_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_workshop_exams_hackathon_award", table_name="workshop_exams")
    op.drop_index("ix_workshop_exams_hackathon_id", table_name="workshop_exams")
    op.drop_column("workshop_exams", "award")
    op.drop_column("workshop_exams", "hackathon_id")
