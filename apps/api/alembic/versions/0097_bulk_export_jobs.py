"""bulk downloads: one table for the export jobs

Revision ID: 0097
Revises: 0096
Create Date: 2026-10-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0097"
down_revision: Union[str, None] = "0096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "bulk_export_jobs",
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("scope_id", _UUID, nullable=True),
        sa.Column("scope_label", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("selection_mode", sa.String(20), nullable=False),
        sa.Column("filters", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("item_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("options", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("total_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("processed_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failures", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("zip_filename", sa.String(255), nullable=True),
        sa.Column("storage_key", sa.String(700), nullable=True, unique=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("download_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bulk_export_jobs_organization_id", "bulk_export_jobs", ["organization_id"])
    op.create_index("ix_bulk_export_jobs_status", "bulk_export_jobs", ["status"])
    op.create_index("ix_bulk_export_jobs_expires_at", "bulk_export_jobs", ["expires_at"])
    op.create_index("ix_bulk_export_jobs_user_created", "bulk_export_jobs", ["requested_by_user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("bulk_export_jobs")
