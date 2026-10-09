"""placements: job feed imported from external job sites

Revision ID: 0064
Revises: 0063
Create Date: 2026-10-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0064"
down_revision: Union[str, None] = "0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "placement_external_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("remote", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("job_type", sa.String(30), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("salary_text", sa.String(120), nullable=True),
        sa.Column("fresher_friendly", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("hidden", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "source", "external_id", name="uq_external_job_source_id"),
    )
    op.create_index("ix_external_jobs_org_active", "placement_external_jobs", ["organization_id", "is_active", "hidden"])
    op.create_index("ix_external_jobs_posted", "placement_external_jobs", ["posted_at"])
    op.create_table(
        "placement_job_feed_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("keywords", postgresql.JSONB(), nullable=False),
        sa.Column("fresher_only", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sources", postgresql.JSONB(), nullable=False),
        sa.Column("source_state", postgresql.JSONB(), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_table("placement_job_feed_settings")
    op.drop_index("ix_external_jobs_posted", table_name="placement_external_jobs")
    op.drop_index("ix_external_jobs_org_active", table_name="placement_external_jobs")
    op.drop_table("placement_external_jobs")
