"""enable required postgres extensions

Revision ID: 0001
Revises:
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgcrypto provides gen_random_uuid(), used as the server-side default
    # for every table's UUID primary key across every module.
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    # pg_trgm enables fast fuzzy/ILIKE search used by list/search endpoints
    # across CRM, students, courses, and inventory modules.
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')


def downgrade() -> None:
    op.execute('DROP EXTENSION IF EXISTS "pg_trgm";')
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto";')
