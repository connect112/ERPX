"""create batch_enrollments table

Revision ID: 0039
Revises: 0038
Create Date: 2026-08-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

batch_enrollment_status_enum = postgresql.ENUM("active", "removed", name="batch_enrollment_status")


def upgrade() -> None:
    batch_enrollment_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "batch_enrollments",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrolled_at", sa.Date(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("active", "removed", name="batch_enrollment_status", create_type=False),
            nullable=False,
        ),
        sa.UniqueConstraint("batch_id", "student_id", name="uq_batch_enrollment_batch_student"),
    )
    op.create_index("ix_batch_enrollments_organization_id", "batch_enrollments", ["organization_id"])
    op.create_index("ix_batch_enrollments_batch_id", "batch_enrollments", ["batch_id"])
    op.create_index("ix_batch_enrollments_student_id", "batch_enrollments", ["student_id"])
    op.create_index("ix_batch_enrollments_status", "batch_enrollments", ["status"])


def downgrade() -> None:
    op.drop_table("batch_enrollments")
    batch_enrollment_status_enum.drop(op.get_bind(), checkfirst=True)
