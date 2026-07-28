"""create internship postings, applications, internships tables

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

posting_status_enum = postgresql.ENUM("draft", "open", "closed", name="internship_posting_status")
application_status_enum = postgresql.ENUM(
    "applied", "shortlisted", "selected", "rejected", "withdrawn", name="internship_application_status"
)
internship_status_enum = postgresql.ENUM(
    "ongoing", "completed", "terminated", name="internship_status"
)

_ALL_ENUMS = [posting_status_enum, application_status_enum, internship_status_enum]


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
        "internship_postings",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("placement_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_months", sa.Integer(), nullable=True),
        sa.Column("stipend", sa.Numeric(12, 2), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("required_skills", sa.Text(), nullable=True),
        sa.Column("application_deadline", sa.Date(), nullable=True),
        sa.Column(
            "status", postgresql.ENUM("draft", "open", "closed", name="internship_posting_status", create_type=False),
            nullable=False, server_default="draft",
        ),
    )
    op.create_index("ix_internship_postings_organization_id", "internship_postings", ["organization_id"])
    op.create_index("ix_internship_postings_company_id", "internship_postings", ["company_id"])
    op.create_index("ix_internship_postings_status", "internship_postings", ["status"])

    op.create_table(
        "internship_applications",
        *_tc(),
        sa.Column("internship_posting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("internship_postings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column(
            "status", postgresql.ENUM("applied", "shortlisted", "selected", "rejected", "withdrawn", name="internship_application_status", create_type=False),
            nullable=False, server_default="applied",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("internship_posting_id", "student_id", name="uq_internship_app_posting_student"),
    )
    op.create_index("ix_internship_applications_internship_posting_id", "internship_applications", ["internship_posting_id"])
    op.create_index("ix_internship_applications_student_id", "internship_applications", ["student_id"])
    op.create_index("ix_internship_applications_status", "internship_applications", ["status"])

    op.create_table(
        "internships",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("internship_applications.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("internship_posting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("internship_postings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mentor_employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("stipend", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "status", postgresql.ENUM("ongoing", "completed", "terminated", name="internship_status", create_type=False),
            nullable=False, server_default="ongoing",
        ),
        sa.Column("feedback", sa.Text(), nullable=True),
    )
    op.create_index("ix_internships_organization_id", "internships", ["organization_id"])
    op.create_index("ix_internships_internship_posting_id", "internships", ["internship_posting_id"])
    op.create_index("ix_internships_student_id", "internships", ["student_id"])
    op.create_index("ix_internships_status", "internships", ["status"])


def downgrade() -> None:
    op.drop_table("internships")
    op.drop_table("internship_applications")
    op.drop_table("internship_postings")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
