"""editable email templates

Revision ID: 0057
Revises: 0056
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0057"
down_revision: Union[str, None] = "0056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "hackathon_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "updated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
    )
    op.create_index("ix_email_templates_organization_id", "email_templates", ["organization_id"])
    op.create_index("ix_email_templates_hackathon_id", "email_templates", ["hackathon_id"])
    op.create_index(
        "uq_email_template_org",
        "email_templates",
        ["organization_id", "key"],
        unique=True,
        postgresql_where=sa.text("hackathon_id IS NULL"),
    )
    op.create_index(
        "uq_email_template_hackathon",
        "email_templates",
        ["organization_id", "key", "hackathon_id"],
        unique=True,
        postgresql_where=sa.text("hackathon_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_email_template_hackathon", table_name="email_templates")
    op.drop_index("uq_email_template_org", table_name="email_templates")
    op.drop_index("ix_email_templates_hackathon_id", table_name="email_templates")
    op.drop_index("ix_email_templates_organization_id", table_name="email_templates")
    op.drop_table("email_templates")
