"""add corporate_clients.user_id for client-portal self-service login

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "corporate_clients",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_corporate_clients_user_id", "corporate_clients", ["user_id"]
    )
    op.create_foreign_key(
        "fk_corporate_clients_user_id_users",
        "corporate_clients",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_corporate_clients_user_id_users", "corporate_clients", type_="foreignkey"
    )
    op.drop_constraint("uq_corporate_clients_user_id", "corporate_clients", type_="unique")
    op.drop_column("corporate_clients", "user_id")
