"""add designation access mapping (linked_role_id, grants_trainer_access)

Revision ID: 0041
Revises: 0040
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A Designation was previously a pure display label with no bearing on
    # system access at all — see modules/hr/models.py's Designation and
    # modules/employees/service.py's invite_employee. These two columns
    # let an admin configure what EmployeeService.invite_employee grants
    # alongside the basic employee-portal login, driven by the invited
    # employee's own designation:
    #   - linked_role_id: also assign this RBAC role (e.g. a "Trainer"
    #     designation's employees could get the "staff" role; nullable —
    #     most designations grant nothing beyond the basic self-service
    #     portal, which every employee gets regardless).
    #   - grants_trainer_access: also create a Trainer record (see
    #     modules/trainers/models.py), the prerequisite for trainer-portal
    #     login — Trainer is keyed by employee_id, layered on Employee
    #     rather than being its own person-record.
    op.add_column(
        "hr_designations",
        sa.Column("linked_role_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_hr_designations_linked_role_id_roles",
        "hr_designations",
        "roles",
        ["linked_role_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "hr_designations",
        sa.Column(
            "grants_trainer_access",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("hr_designations", "grants_trainer_access")
    op.drop_constraint("fk_hr_designations_linked_role_id_roles", "hr_designations", type_="foreignkey")
    op.drop_column("hr_designations", "linked_role_id")
