"""add external_reference to user_profiles

Revision ID: 0040
Revises: 0039
Create Date: 2026-08-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotency key for server-to-server account provisioning (e.g. the
    # Pentrix-share -> ERPX internal provisioning endpoint): stores the
    # caller's own reference (a Pentrix payment id) on the UserProfile
    # created for it, so a retried provisioning call can be recognized and
    # short-circuited rather than creating a duplicate user. Nullable and
    # only ever set for profiles created through such a flow — most
    # UserProfile rows (manually created staff/admin accounts) have none.
    # A plain unique index (not partial) is fine here: Postgres unique
    # indexes already permit any number of NULLs, only enforcing uniqueness
    # among the non-NULL values.
    op.add_column(
        "user_profiles", sa.Column("external_reference", sa.String(length=255), nullable=True)
    )
    op.create_index(
        "ix_user_profiles_external_reference",
        "user_profiles",
        ["external_reference"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_user_profiles_external_reference", table_name="user_profiles")
    op.drop_column("user_profiles", "external_reference")
