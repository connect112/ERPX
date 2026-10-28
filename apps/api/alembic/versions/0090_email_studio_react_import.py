"""email studio: soft-deleted templates, a protection flag for system templates, and imported React Email source

Revision ID: 0090
Revises: 0089
Create Date: 2026-10-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0090"
down_revision: Union[str, None] = "0089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A deleted template is hidden, not removed: its versions and the send history that points at it stay, and it can be restored.
    op.add_column("email_studio_templates", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "email_studio_templates",
        sa.Column("deleted_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    # System templates are protected by this flag, never by their name.
    op.add_column("email_studio_templates", sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_index("ix_email_templates_org_deleted", "email_studio_templates", ["organization_id", "deleted_at"])
    # The React Email code exactly as it was pasted. What is sent is the HTML built from it (body_html).
    op.add_column("email_studio_versions", sa.Column("react_source", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("email_studio_versions", "react_source")
    op.drop_index("ix_email_templates_org_deleted", table_name="email_studio_templates")
    op.drop_column("email_studio_templates", "is_system")
    op.drop_column("email_studio_templates", "deleted_by_user_id")
    op.drop_column("email_studio_templates", "deleted_at")
