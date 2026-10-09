"""social media phase 2b: image assets, post design and artwork

Revision ID: 0071
Revises: 0070
Create Date: 2026-10-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0071"
down_revision: Union[str, None] = "0070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "social_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("storage_key", sa.String(300), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("bytes_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("alt_text", sa.String(420), server_default="", nullable=False),
        sa.Column("synthetic", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("provenance", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.UniqueConstraint("storage_key", name="uq_social_assets_storage_key"),
    )
    op.create_index("ix_social_assets_organization_id", "social_assets", ["organization_id"])
    op.create_index("ix_social_assets_org_kind", "social_assets", ["organization_id", "kind"])
    op.add_column("social_posts", sa.Column("design", postgresql.JSONB(), server_default="{}", nullable=False))
    op.add_column("social_posts", sa.Column("artwork", postgresql.JSONB(), server_default="{}", nullable=False))


def downgrade() -> None:
    op.drop_column("social_posts", "artwork")
    op.drop_column("social_posts", "design")
    op.drop_table("social_assets")
