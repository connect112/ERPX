"""workshop exam certificate template

Revision ID: 0049
Revises: 0048
Create Date: 2026-10-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workshop_exams",
        sa.Column("has_certificate_template", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("workshop_exams", sa.Column("certificate_layout", postgresql.JSONB(), nullable=True))
    op.create_table(
        "workshop_exam_certificate_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("exam_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workshop_exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.UniqueConstraint("exam_id", name="uq_workshop_exam_certificate_templates_exam_id"),
    )


def downgrade() -> None:
    op.drop_table("workshop_exam_certificate_templates")
    op.drop_column("workshop_exams", "certificate_layout")
    op.drop_column("workshop_exams", "has_certificate_template")
