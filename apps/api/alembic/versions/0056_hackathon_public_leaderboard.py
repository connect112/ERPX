"""hackathon public leaderboard link

Revision ID: 0056
Revises: 0055
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: Union[str, None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hackathons", sa.Column("leaderboard_share_enabled", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("hackathons", sa.Column("leaderboard_slug", sa.String(length=60), nullable=True))
    op.add_column(
        "hackathons", sa.Column("leaderboard_show_members", sa.Boolean(), server_default="false", nullable=False)
    )
    op.create_unique_constraint("uq_hackathon_leaderboard_slug", "hackathons", ["leaderboard_slug"])


def downgrade() -> None:
    op.drop_constraint("uq_hackathon_leaderboard_slug", "hackathons", type_="unique")
    op.drop_column("hackathons", "leaderboard_show_members")
    op.drop_column("hackathons", "leaderboard_slug")
    op.drop_column("hackathons", "leaderboard_share_enabled")
