"""
Team join codes.

A team is joined by typing its code, which only the organiser and the team's own members can
see. Codes are six characters from an alphabet without look-alikes (no 0/O, 1/I/L), unique within
a hackathon, and can be replaced by the organiser if one gets out.
"""

import re
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from modules.hackathons.models import Team

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
_ATTEMPTS = 8


def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(value: str) -> str:
    """What the student typed, as a code: case and spacing / dashes don't matter."""
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


async def _name_taken(db: AsyncSession, hackathon_id: uuid.UUID, name: str) -> bool:
    return (
        await db.execute(select(Team.id).where(Team.hackathon_id == hackathon_id, Team.name == name))
    ).first() is not None


async def create_team_with_code(db: AsyncSession, hackathon_id: uuid.UUID, created_by_student_id: uuid.UUID, name: str) -> Team:
    """Insert a team with a fresh code. A taken team name is reported plainly; a code that happens to
    collide with another team's is simply redrawn."""
    for _ in range(_ATTEMPTS):
        try:
            async with db.begin_nested():
                team = Team(
                    hackathon_id=hackathon_id,
                    created_by_student_id=created_by_student_id,
                    name=name,
                    join_code=new_code(),
                )
                db.add(team)
                await db.flush()
            await db.refresh(team)
            return team
        except IntegrityError:
            if await _name_taken(db, hackathon_id, name):
                raise ConflictError(f'A team named "{name}" already exists. Please choose another name.') from None
    raise ConflictError("Could not make a team code. Please try again.")


async def replace_code(db: AsyncSession, team: Team) -> str:
    """Give the team a new code (the old one stops working)."""
    for _ in range(_ATTEMPTS):
        try:
            async with db.begin_nested():
                team.join_code = new_code()
                await db.flush()
            return team.join_code
        except IntegrityError:
            continue
    raise ConflictError("Could not make a team code. Please try again.")
