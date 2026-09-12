"""create placement_job_posting_matches table

Revision ID: 0042
Revises: 0041
Create Date: 2026-08-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tc():
    return [
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "placement_job_posting_matches",
        *_tc(),
        sa.Column(
            "canonical_posting_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("placement_job_postings.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "duplicate_posting_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("placement_job_postings.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("similarity_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("matched_fields", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "canonical_posting_id", "duplicate_posting_id", name="uq_job_posting_match_pair"
        ),
    )
    op.create_index(
        "ix_placement_job_posting_matches_canonical_posting_id",
        "placement_job_posting_matches",
        ["canonical_posting_id"],
    )
    op.create_index(
        "ix_placement_job_posting_matches_duplicate_posting_id",
        "placement_job_posting_matches",
        ["duplicate_posting_id"],
    )


def downgrade() -> None:
    op.drop_table("placement_job_posting_matches")
