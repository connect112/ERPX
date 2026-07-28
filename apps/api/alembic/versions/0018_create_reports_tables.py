"""create reports tables (scheduled reports, report executions)

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

report_export_format_enum = postgresql.ENUM("json", "csv", "excel", "pdf", name="report_export_format")
report_execution_status_enum = postgresql.ENUM("success", "failed", name="report_execution_status")
report_schedule_frequency_enum = postgresql.ENUM("daily", "weekly", "monthly", name="report_schedule_frequency")

_ALL_ENUMS = [report_export_format_enum, report_execution_status_enum, report_schedule_frequency_enum]


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
        "scheduled_reports",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("report_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("export_format", postgresql.ENUM("json", "csv", "excel", "pdf", name="report_export_format", create_type=False), nullable=False),
        sa.Column("frequency", postgresql.ENUM("daily", "weekly", "monthly", name="report_schedule_frequency", create_type=False), nullable=False),
        sa.Column("recipient_emails", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scheduled_reports_organization_id", "scheduled_reports", ["organization_id"])
    op.create_index("ix_scheduled_reports_report_key", "scheduled_reports", ["report_key"])
    op.create_index("ix_scheduled_reports_next_run_at", "scheduled_reports", ["next_run_at"])

    op.create_table(
        "report_executions",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("executed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scheduled_report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scheduled_reports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("report_key", sa.String(length=100), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("export_format", postgresql.ENUM("json", "csv", "excel", "pdf", name="report_export_format", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("success", "failed", name="report_execution_status", create_type=False), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_report_executions_organization_id", "report_executions", ["organization_id"])
    op.create_index("ix_report_executions_scheduled_report_id", "report_executions", ["scheduled_report_id"])
    op.create_index("ix_report_executions_report_key", "report_executions", ["report_key"])
    op.create_index("ix_report_executions_status", "report_executions", ["status"])


def downgrade() -> None:
    op.drop_table("report_executions")
    op.drop_table("scheduled_reports")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
