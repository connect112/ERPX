"""internship certificates: which certificate each student is eligible for

Revision ID: 0086
Revises: 0085
Create Date: 2026-10-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0086"
down_revision: Union[str, None] = "0085"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    postgresql.ENUM("participation", "completion", name="internship_certificate_kind").create(op.get_bind(), checkfirst=True)
    op.create_table(
        "internship_certificate_eligibility",
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selection_id", _UUID, sa.ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", postgresql.ENUM(name="internship_certificate_kind", create_type=False), nullable=False),
        sa.Column("chosen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chosen_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("internship_id", "selection_id", name="uq_certificate_eligibility_student"),
    )
    for column in ("organization_id", "internship_id", "selection_id"):
        op.create_index(f"ix_internship_certificate_eligibility_{column}", "internship_certificate_eligibility", [column])


def downgrade() -> None:
    op.drop_table("internship_certificate_eligibility")
    postgresql.ENUM(name="internship_certificate_kind").drop(op.get_bind(), checkfirst=True)
