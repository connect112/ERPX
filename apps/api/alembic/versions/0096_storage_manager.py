"""storage manager: trash and the append-only deletion log

Revision ID: 0096
Revises: 0095
Create Date: 2026-10-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0096"
down_revision: Union[str, None] = "0095"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _base() -> list:
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "storage_trash",
        *_base(),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("original_key", sa.String(700), nullable=False),
        sa.Column("trash_key", sa.String(800), nullable=False, unique=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(150), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("etag", sa.String(80), nullable=True),
        sa.Column("evidence", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("deleted_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_storage_trash_organization_id", "storage_trash", ["organization_id"])
    op.create_index("ix_storage_trash_deleted_at", "storage_trash", ["deleted_at"])

    op.create_table(
        "storage_deletion_log",
        *_base(),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("object_key", sa.String(800), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("trash_id", _UUID, nullable=True),
        sa.Column("evidence", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
    )
    op.create_index("ix_storage_deletion_log_organization_id", "storage_deletion_log", ["organization_id"])
    op.create_index("ix_storage_deletion_log_created_at", "storage_deletion_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("storage_deletion_log")
    op.drop_table("storage_trash")
