"""hackathon team join codes

Revision ID: 0055
Revises: 0054
Create Date: 2026-10-07

"""
import secrets
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0055"
down_revision: Union[str, None] = "0054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# No 0/O or 1/I/L, so a code read out loud or copied by hand can't be mistyped as another character.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_LENGTH = 6


def upgrade() -> None:
    op.add_column("hackathon_teams", sa.Column("join_code", sa.String(length=12), nullable=True))
    bind = op.get_bind()
    teams = bind.execute(sa.text("SELECT id, hackathon_id FROM hackathon_teams")).fetchall()
    used: set[tuple] = set()
    for team_id, hackathon_id in teams:
        while True:
            code = "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))
            if (hackathon_id, code) not in used:
                used.add((hackathon_id, code))
                break
        bind.execute(sa.text("UPDATE hackathon_teams SET join_code = :code WHERE id = :id"), {"code": code, "id": team_id})
    op.alter_column("hackathon_teams", "join_code", existing_type=sa.String(length=12), nullable=False)
    op.create_unique_constraint("uq_hackathon_team_join_code", "hackathon_teams", ["hackathon_id", "join_code"])


def downgrade() -> None:
    op.drop_constraint("uq_hackathon_team_join_code", "hackathon_teams", type_="unique")
    op.drop_column("hackathon_teams", "join_code")
