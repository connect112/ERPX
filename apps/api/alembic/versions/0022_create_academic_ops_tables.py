"""create trainers, classrooms, batches, timetable_entries, live_classes tables

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

classroom_type_enum = postgresql.ENUM("physical", "virtual", name="classroom_type")
batch_status_enum = postgresql.ENUM("upcoming", "ongoing", "completed", "cancelled", name="batch_status")
day_of_week_enum = postgresql.ENUM(
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", name="day_of_week"
)
live_class_status_enum = postgresql.ENUM(
    "scheduled", "live", "completed", "cancelled", name="live_class_status"
)

_ALL_ENUMS = [classroom_type_enum, batch_status_enum, day_of_week_enum, live_class_status_enum]


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

    # ---- trainers ----
    op.create_table(
        "trainers",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("specializations", sa.Text(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("max_weekly_hours", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_trainers_organization_id", "trainers", ["organization_id"])

    # ---- classrooms ----
    op.create_table(
        "classrooms",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("classroom_type", postgresql.ENUM("physical", "virtual", name="classroom_type", create_type=False), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("meeting_link", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_classroom_org_code"),
    )
    op.create_index("ix_classrooms_organization_id", "classrooms", ["organization_id"])
    op.create_index("ix_classrooms_branch_id", "classrooms", ["branch_id"])

    # ---- batches ----
    op.create_table(
        "batches",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trainer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("status", postgresql.ENUM("upcoming", "ongoing", "completed", "cancelled", name="batch_status", create_type=False), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.UniqueConstraint("organization_id", "code", name="uq_batch_org_code"),
    )
    op.create_index("ix_batches_organization_id", "batches", ["organization_id"])
    op.create_index("ix_batches_branch_id", "batches", ["branch_id"])
    op.create_index("ix_batches_course_id", "batches", ["course_id"])
    op.create_index("ix_batches_trainer_id", "batches", ["trainer_id"])
    op.create_index("ix_batches_status", "batches", ["status"])

    # ---- timetable_entries ----
    op.create_table(
        "timetable_entries",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("classroom_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("classrooms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trainer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("day_of_week", postgresql.ENUM("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", name="day_of_week", create_type=False), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_timetable_entries_organization_id", "timetable_entries", ["organization_id"])
    op.create_index("ix_timetable_entries_batch_id", "timetable_entries", ["batch_id"])
    op.create_index("ix_timetable_entries_classroom_id", "timetable_entries", ["classroom_id"])
    op.create_index("ix_timetable_entries_trainer_id", "timetable_entries", ["trainer_id"])

    # ---- live_classes ----
    op.create_table(
        "live_classes",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trainer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("meeting_link", sa.String(length=512), nullable=False),
        sa.Column("recording_url", sa.String(length=512), nullable=True),
        sa.Column("status", postgresql.ENUM("scheduled", "live", "completed", "cancelled", name="live_class_status", create_type=False), nullable=False),
    )
    op.create_index("ix_live_classes_organization_id", "live_classes", ["organization_id"])
    op.create_index("ix_live_classes_batch_id", "live_classes", ["batch_id"])
    op.create_index("ix_live_classes_trainer_id", "live_classes", ["trainer_id"])
    op.create_index("ix_live_classes_status", "live_classes", ["status"])


def downgrade() -> None:
    op.drop_table("live_classes")
    op.drop_table("timetable_entries")
    op.drop_table("batches")
    op.drop_table("classrooms")
    op.drop_table("trainers")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
