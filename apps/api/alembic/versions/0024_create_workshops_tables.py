"""create workshops and workshop_registrations tables

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

workshop_mode_enum = postgresql.ENUM("physical", "virtual", name="workshop_mode")
workshop_status_enum = postgresql.ENUM(
    "draft", "published", "ongoing", "completed", "cancelled", name="workshop_status"
)
registration_status_enum = postgresql.ENUM(
    "registered", "attended", "no_show", "cancelled", name="workshop_registration_status"
)

_ALL_ENUMS = [workshop_mode_enum, workshop_status_enum, registration_status_enum]


def _tc():
    return [
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "workshops",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trainer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mode", postgresql.ENUM("physical", "virtual", name="workshop_mode", create_type=False), nullable=False, server_default="physical"),
        sa.Column("venue", sa.String(length=255), nullable=True),
        sa.Column("meeting_link", sa.String(length=512), nullable=True),
        sa.Column("workshop_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column(
            "status", postgresql.ENUM("draft", "published", "ongoing", "completed", "cancelled", name="workshop_status", create_type=False),
            nullable=False, server_default="draft",
        ),
        sa.UniqueConstraint("organization_id", "code", name="uq_workshop_org_code"),
    )
    op.create_index("ix_workshops_organization_id", "workshops", ["organization_id"])
    op.create_index("ix_workshops_trainer_id", "workshops", ["trainer_id"])
    op.create_index("ix_workshops_workshop_date", "workshops", ["workshop_date"])
    op.create_index("ix_workshops_status", "workshops", ["status"])

    op.create_table(
        "workshop_registrations",
        *_tc(),
        sa.Column("workshop_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contact_name", sa.String(length=255), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", postgresql.ENUM("registered", "attended", "no_show", "cancelled", name="workshop_registration_status", create_type=False),
            nullable=False, server_default="registered",
        ),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("workshop_id", "student_id", name="uq_workshop_registration_student"),
    )
    op.create_index("ix_workshop_registrations_workshop_id", "workshop_registrations", ["workshop_id"])
    op.create_index("ix_workshop_registrations_student_id", "workshop_registrations", ["student_id"])
    op.create_index("ix_workshop_registrations_status", "workshop_registrations", ["status"])


def downgrade() -> None:
    op.drop_table("workshop_registrations")
    op.drop_table("workshops")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
