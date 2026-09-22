"""add organization_id to roles (roles are now per-organization, not global)

Revision ID: 0042
Revises: 0041
Create Date: 2026-09-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL organization_id = a system role template (Super Admin,
    # Administrator, Staff, Student, Trainer, ...) shipped by the platform
    # and shared read-only across every organization. A custom role an
    # org's own admin creates gets that org's id and is only ever visible,
    # editable, or assignable within that org — see
    # modules/authorization/service.py's ownership checks. Every existing
    # row predates this column and is a system role, so it stays NULL.
    op.add_column(
        "roles",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_roles_organization_id_organizations",
        "roles",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_roles_organization_id", "roles", ["organization_id"])

    op.drop_constraint("uq_roles_slug", "roles", type_="unique")
    op.create_unique_constraint("uq_role_org_slug", "roles", ["organization_id", "slug"])


def downgrade() -> None:
    op.drop_constraint("uq_role_org_slug", "roles", type_="unique")
    op.create_unique_constraint("uq_roles_slug", "roles", ["slug"])
    op.drop_index("ix_roles_organization_id", table_name="roles")
    op.drop_constraint("fk_roles_organization_id_organizations", "roles", type_="foreignkey")
    op.drop_column("roles", "organization_id")
