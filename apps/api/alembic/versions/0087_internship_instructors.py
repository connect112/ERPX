"""internship instructors: trainers assigned to an internship with an access window

Revision ID: 0087
Revises: 0086
Create Date: 2026-10-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0087"
down_revision: Union[str, None] = "0086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "internship_instructors",
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trainer_id", _UUID, sa.ForeignKey("trainers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("granted_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("internship_id", "trainer_id", name="uq_internship_instructor"),
    )
    for column in ("organization_id", "internship_id", "trainer_id"):
        op.create_index(f"ix_internship_instructors_{column}", "internship_instructors", [column])


def downgrade() -> None:
    op.drop_table("internship_instructors")
