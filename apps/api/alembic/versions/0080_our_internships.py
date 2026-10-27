"""our internships: the internship programmes and their shortlists of selected students

Revision ID: 0080
Revises: 0079
Create Date: 2026-10-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0080"
down_revision: Union[str, None] = "0079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _id_and_timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    postgresql.ENUM("institution", "all", name="our_internship_scope").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("selecting", "offers_released", "closed", name="our_internship_status").create(
        op.get_bind(), checkfirst=True
    )
    op.create_table(
        "our_internships",
        *_id_and_timestamps(),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope", postgresql.ENUM(name="our_internship_scope", create_type=False), nullable=False),
        sa.Column("institution_id", _UUID, sa.ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_id", _UUID, sa.ForeignKey("institution_events.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="our_internship_status", create_type=False),
            server_default="selecting",
            nullable=False,
        ),
    )
    op.create_index("ix_our_internships_organization_id", "our_internships", ["organization_id"])
    op.create_index("ix_our_internships_institution_id", "our_internships", ["institution_id"])
    op.create_index("ix_our_internships_event_id", "our_internships", ["event_id"])
    op.create_index("ix_our_internships_status", "our_internships", ["status"])

    op.create_table(
        "our_internship_selections",
        *_id_and_timestamps(),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", _UUID, sa.ForeignKey("institution_students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selected_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint("internship_id", "student_id", name="uq_internship_selection"),
    )
    op.create_index("ix_our_internship_selections_organization_id", "our_internship_selections", ["organization_id"])
    op.create_index("ix_our_internship_selections_internship_id", "our_internship_selections", ["internship_id"])
    op.create_index("ix_our_internship_selections_student_id", "our_internship_selections", ["student_id"])


def downgrade() -> None:
    op.drop_table("our_internship_selections")
    op.drop_table("our_internships")
    postgresql.ENUM(name="our_internship_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="our_internship_scope").drop(op.get_bind(), checkfirst=True)
