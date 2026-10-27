"""our internships: the offer letter template, its email, and each selected student's offer status

Revision ID: 0081
Revises: 0080
Create Date: 2026-10-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0081"
down_revision: Union[str, None] = "0080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("our_internships", sa.Column("offer_template_filename", sa.String(255), nullable=True))
    op.add_column("our_internships", sa.Column("offer_template_size", sa.Integer(), nullable=True))
    op.add_column("our_internships", sa.Column("offer_template_pages", sa.Integer(), nullable=True))
    op.add_column("our_internships", sa.Column("offer_template_data", sa.LargeBinary(), nullable=True))
    op.add_column("our_internships", sa.Column("offer_layout", postgresql.JSONB(), nullable=True))
    op.add_column("our_internships", sa.Column("offer_email_subject", sa.String(255), nullable=True))
    op.add_column("our_internships", sa.Column("offer_email_body", sa.Text(), nullable=True))
    op.add_column("our_internships", sa.Column("offer_date", sa.Date(), nullable=True))
    op.add_column("our_internships", sa.Column("offers_released_at", sa.DateTime(timezone=True), nullable=True))

    postgresql.ENUM("not_sent", "queued", "sent", "failed", name="our_internship_offer_status").create(
        op.get_bind(), checkfirst=True
    )
    op.add_column("our_internship_selections", sa.Column("offer_reference", sa.String(50), nullable=True))
    op.add_column(
        "our_internship_selections",
        sa.Column(
            "offer_status",
            postgresql.ENUM(name="our_internship_offer_status", create_type=False),
            server_default="not_sent",
            nullable=False,
        ),
    )
    op.add_column("our_internship_selections", sa.Column("offer_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "our_internship_selections", sa.Column("offer_attempts", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("our_internship_selections", sa.Column("offer_error", sa.String(255), nullable=True))


def downgrade() -> None:
    for column in ("offer_error", "offer_attempts", "offer_sent_at", "offer_status", "offer_reference"):
        op.drop_column("our_internship_selections", column)
    postgresql.ENUM(name="our_internship_offer_status").drop(op.get_bind(), checkfirst=True)
    for column in (
        "offers_released_at",
        "offer_date",
        "offer_email_body",
        "offer_email_subject",
        "offer_layout",
        "offer_template_data",
        "offer_template_pages",
        "offer_template_size",
        "offer_template_filename",
    ):
        op.drop_column("our_internships", column)
