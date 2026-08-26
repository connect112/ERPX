"""add job-aggregation fields to placement_job_postings

Revision ID: 0041
Revises: 0040
Create Date: 2026-08-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "placement_job_postings",
        sa.Column("source", sa.String(length=50), nullable=False, server_default="manual"),
    )
    op.add_column(
        "placement_job_postings", sa.Column("external_id", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "placement_job_postings", sa.Column("source_url", sa.String(length=1000), nullable=True)
    )
    op.add_column(
        "placement_job_postings",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Consecutive-pull-absence counter the aggregation pipeline uses to flip
    # a delisted external posting to `closed` (never deleted) after 3 misses
    # — see modules/placements/aggregation_service.py.
    op.add_column(
        "placement_job_postings",
        sa.Column("absence_streak", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_index(
        "ix_placement_job_postings_source", "placement_job_postings", ["source"]
    )
    # Partial unique index, not a plain UniqueConstraint: this is the upsert
    # key the aggregation pipeline dedupes new/refreshed postings against,
    # scoped per organization (the same external posting legitimately gets
    # one row per active org — see aggregation_service.py's fan-out step).
    # The WHERE clause documents intent (external_id is only ever set for
    # aggregated rows) even though a plain composite index would already
    # tolerate unlimited NULLs under Postgres' standard NULL-distinctness.
    op.create_index(
        "uq_placement_job_postings_org_source_external_id",
        "placement_job_postings",
        ["organization_id", "source", "external_id"],
        unique=True,
        postgresql_where=sa.text("source IS NOT NULL AND external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_placement_job_postings_org_source_external_id",
        table_name="placement_job_postings",
    )
    op.drop_index("ix_placement_job_postings_source", table_name="placement_job_postings")
    op.drop_column("placement_job_postings", "absence_streak")
    op.drop_column("placement_job_postings", "last_seen_at")
    op.drop_column("placement_job_postings", "source_url")
    op.drop_column("placement_job_postings", "external_id")
    op.drop_column("placement_job_postings", "source")
