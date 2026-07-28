"""create students table

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

student_status_enum = postgresql.ENUM(
    "active", "on_hold", "completed", "dropped", "transferred", name="student_status"
)


def upgrade() -> None:
    student_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "students",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("admission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_admissions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_code", sa.String(length=30), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column(
            "gender",
            postgresql.ENUM(
                "male", "female", "other", "prefer_not_to_say",
                name="gender", create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("guardian_name", sa.String(length=255), nullable=True),
        sa.Column("guardian_phone", sa.String(length=32), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("course_name", sa.String(length=255), nullable=False),
        sa.Column("batch_name", sa.String(length=150), nullable=True),
        sa.Column("enrollment_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "on_hold", "completed", "dropped", "transferred",
                name="student_status", create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "student_code", name="uq_student_org_code"),
        sa.UniqueConstraint("admission_id", name="uq_students_admission_id"),
        sa.UniqueConstraint("user_id", name="uq_students_user_id"),
    )
    op.create_index("ix_students_organization_id", "students", ["organization_id"])
    op.create_index("ix_students_branch_id", "students", ["branch_id"])
    op.create_index("ix_students_status", "students", ["status"])
    op.create_index("ix_students_student_code", "students", ["student_code"])


def downgrade() -> None:
    op.drop_table("students")
    student_status_enum.drop(op.get_bind(), checkfirst=True)
