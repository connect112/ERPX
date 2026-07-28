"""create approval workflow, step, request, action tables

Revision ID: 0030
Revises: 0029
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

request_status_enum = postgresql.ENUM(
    "pending", "approved", "rejected", "cancelled", name="approval_request_status"
)
decision_enum = postgresql.ENUM("approved", "rejected", name="approval_decision")

_ALL_ENUMS = [request_status_enum, decision_enum]


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
        "approval_workflows",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "entity_type", "name", name="uq_workflow_org_entity_name"),
    )
    op.create_index("ix_approval_workflows_organization_id", "approval_workflows", ["organization_id"])
    op.create_index("ix_approval_workflows_entity_type", "approval_workflows", ["entity_type"])

    op.create_table(
        "approval_steps",
        *_tc(),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("approver_role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("workflow_id", "step_order", name="uq_approval_step_workflow_order"),
    )
    op.create_index("ix_approval_steps_workflow_id", "approval_steps", ["workflow_id"])

    op.create_table(
        "approval_requests",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_step_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status", postgresql.ENUM("pending", "approved", "rejected", "cancelled", name="approval_request_status", create_type=False),
            nullable=False, server_default="pending",
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approval_requests_organization_id", "approval_requests", ["organization_id"])
    op.create_index("ix_approval_requests_workflow_id", "approval_requests", ["workflow_id"])
    op.create_index("ix_approval_requests_entity_type", "approval_requests", ["entity_type"])
    op.create_index("ix_approval_requests_entity_id", "approval_requests", ["entity_id"])
    op.create_index("ix_approval_requests_requested_by_user_id", "approval_requests", ["requested_by_user_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])

    op.create_table(
        "approval_actions",
        *_tc(),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "decision", postgresql.ENUM("approved", "rejected", name="approval_decision", create_type=False),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_approval_actions_request_id", "approval_actions", ["request_id"])


def downgrade() -> None:
    op.drop_table("approval_actions")
    op.drop_table("approval_requests")
    op.drop_table("approval_steps")
    op.drop_table("approval_workflows")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
