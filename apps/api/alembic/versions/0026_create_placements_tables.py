"""create placement companies, job postings, applications tables

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

job_type_enum = postgresql.ENUM(
    "full_time", "part_time", "internship", "contract", name="placement_job_type"
)
posting_status_enum = postgresql.ENUM("draft", "open", "closed", name="placement_job_posting_status")
application_status_enum = postgresql.ENUM(
    "applied", "shortlisted", "interview_scheduled", "offered", "rejected", "withdrawn",
    name="placement_application_status",
)

_ALL_ENUMS = [job_type_enum, posting_status_enum, application_status_enum]


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
        "placement_companies",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=150), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("contact_person_name", sa.String(length=255), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_placement_companies_organization_id", "placement_companies", ["organization_id"])

    op.create_table(
        "placement_job_postings",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("placement_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "job_type", postgresql.ENUM("full_time", "part_time", "internship", "contract", name="placement_job_type", create_type=False),
            nullable=False, server_default="full_time",
        ),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("required_skills", sa.Text(), nullable=True),
        sa.Column("application_deadline", sa.Date(), nullable=True),
        sa.Column(
            "status", postgresql.ENUM("draft", "open", "closed", name="placement_job_posting_status", create_type=False),
            nullable=False, server_default="draft",
        ),
    )
    op.create_index("ix_placement_job_postings_organization_id", "placement_job_postings", ["organization_id"])
    op.create_index("ix_placement_job_postings_company_id", "placement_job_postings", ["company_id"])
    op.create_index("ix_placement_job_postings_status", "placement_job_postings", ["status"])

    op.create_table(
        "placement_applications",
        *_tc(),
        sa.Column("job_posting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("placement_job_postings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column(
            "status", postgresql.ENUM("applied", "shortlisted", "interview_scheduled", "offered", "rejected", "withdrawn", name="placement_application_status", create_type=False),
            nullable=False, server_default="applied",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("job_posting_id", "student_id", name="uq_application_posting_student"),
    )
    op.create_index("ix_placement_applications_job_posting_id", "placement_applications", ["job_posting_id"])
    op.create_index("ix_placement_applications_student_id", "placement_applications", ["student_id"])
    op.create_index("ix_placement_applications_status", "placement_applications", ["status"])


def downgrade() -> None:
    op.drop_table("placement_applications")
    op.drop_table("placement_job_postings")
    op.drop_table("placement_companies")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
