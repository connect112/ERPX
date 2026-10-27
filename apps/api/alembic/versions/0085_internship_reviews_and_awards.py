"""internship project reviews, final marks and awards

Revision ID: 0085
Revises: 0084
Create Date: 2026-10-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0085"
down_revision: Union[str, None] = "0084"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("internship_projects", sa.Column("review_factors", postgresql.JSONB(), server_default="[]", nullable=False))
    op.add_column("internship_projects", sa.Column("max_marks", sa.Integer(), server_default="100", nullable=False))
    op.add_column("internship_project_submissions", sa.Column("final_marks", sa.Numeric(7, 2), nullable=True))
    op.add_column("internship_project_submissions", sa.Column("final_feedback", sa.Text(), nullable=True))
    op.add_column("internship_project_submissions", sa.Column("final_published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "internship_project_submissions",
        sa.Column("finalized_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    op.create_table(
        "internship_project_reviews",
        *_base(),
        sa.Column("submission_id", _UUID, sa.ForeignKey("internship_project_submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("factor_scores", postgresql.JSONB(), nullable=True),
        sa.Column("total", sa.Numeric(7, 2), nullable=False),
        sa.Column("max_total", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
    )
    for column in ("organization_id", "submission_id"):
        op.create_index(f"ix_internship_project_reviews_{column}", "internship_project_reviews", [column])

    op.create_table(
        "internship_awards",
        *_base(),
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    for column in ("organization_id", "internship_id"):
        op.create_index(f"ix_internship_awards_{column}", "internship_awards", [column])

    op.create_table(
        "internship_award_grants",
        *_base(),
        sa.Column("award_id", _UUID, sa.ForeignKey("internship_awards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selection_id", _UUID, sa.ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("award_id", "selection_id", name="uq_award_grant"),
    )
    for column in ("organization_id", "award_id", "selection_id"):
        op.create_index(f"ix_internship_award_grants_{column}", "internship_award_grants", [column])


def downgrade() -> None:
    op.drop_table("internship_award_grants")
    op.drop_table("internship_awards")
    op.drop_table("internship_project_reviews")
    for column in ("finalized_by_user_id", "final_published_at", "final_feedback", "final_marks"):
        op.drop_column("internship_project_submissions", column)
    op.drop_column("internship_projects", "max_marks")
    op.drop_column("internship_projects", "review_factors")
