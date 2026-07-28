"""add sms value to followup_type enum

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-26

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction as a
    # later statement that uses the new value; Alembic's per-migration
    # transaction boundary and the fact "sms" isn't used until a later
    # request make this safe on PostgreSQL 12+ (see 0013 for precedent).
    op.execute("ALTER TYPE followup_type ADD VALUE IF NOT EXISTS 'sms'")


def downgrade() -> None:
    # PostgreSQL has no ALTER TYPE ... DROP VALUE; removing an enum value
    # requires rebuilding the type, which isn't worth it for a downgrade
    # path that's realistically never used against a live database with
    # 'sms' rows already in it. Leaving the value in place on downgrade is
    # the same tradeoff every other enum-add migration in this project makes.
    pass
