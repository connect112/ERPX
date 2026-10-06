import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.hackathons.models import Hackathon, HackathonStatus, Team, TeamMember
from modules.hackathons.repository import (
    HackathonRepository,
    TeamMemberRepository,
    TeamRepository,
)
from modules.hackathons.team_codes import create_team_with_code, normalize_code
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


class HackathonService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = HackathonRepository(db)

    async def create_hackathon(self, organization_id: uuid.UUID, code: str, **fields) -> Hackathon:
        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"A hackathon with code '{code}' already exists.")
        hackathon = await self.repo.create(organization_id=organization_id, code=code, **fields)
        logger.info("hackathon_created", hackathon_id=str(hackathon.id))
        return hackathon

    async def get_hackathon(self, hackathon_id: uuid.UUID, organization_id: uuid.UUID) -> Hackathon:
        hackathon = await self.repo.get_by_id(hackathon_id, organization_id)
        if not hackathon:
            raise NotFoundError("Hackathon", hackathon_id)
        return hackathon

    async def list_hackathons(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_hackathon(
        self, hackathon_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Hackathon:
        hackathon = await self.get_hackathon(hackathon_id, organization_id)
        updated = await self.repo.update(hackathon, **fields)
        logger.info("hackathon_updated", hackathon_id=str(hackathon_id))
        return updated

    async def change_status(
        self, hackathon_id: uuid.UUID, organization_id: uuid.UUID, status: HackathonStatus
    ) -> Hackathon:
        hackathon = await self.get_hackathon(hackathon_id, organization_id)
        updated = await self.repo.update(hackathon, status=status)
        logger.info("hackathon_status_changed", hackathon_id=str(hackathon_id), status=status.value)
        return updated

    async def delete_hackathon(self, hackathon_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        hackathon = await self.get_hackathon(hackathon_id, organization_id)
        await self.repo.delete(hackathon)
        logger.info("hackathon_deleted", hackathon_id=str(hackathon_id))


class TeamService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TeamRepository(db)
        self.member_repo = TeamMemberRepository(db)
        self.hackathon_repo = HackathonRepository(db)
        self.student_repo = StudentRepository(db)

    async def _get_registerable_hackathon(
        self, hackathon_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Hackathon:
        hackathon = await self.hackathon_repo.get_by_id(hackathon_id, organization_id)
        if not hackathon:
            raise NotFoundError("Hackathon", hackathon_id)
        if hackathon.status != HackathonStatus.REGISTRATION_OPEN:
            raise ValidationError("This hackathon is not open for team registration.")
        if date.today() > hackathon.registration_deadline:
            raise ValidationError("The registration deadline for this hackathon has passed.")
        return hackathon

    async def create_team(
        self, organization_id: uuid.UUID, hackathon_id: uuid.UUID, student_id: uuid.UUID, name: str
    ) -> Team:
        await self._get_registerable_hackathon(hackathon_id, organization_id)

        existing_team = await self.repo.get_for_student_in_hackathon(hackathon_id, student_id)
        if existing_team:
            raise ConflictError("You are already part of a team for this hackathon.")

        # Two teams can't share a name in one hackathon; that is reported plainly
        # (and the team gets its join code) instead of surfacing as a server error.
        team = await create_team_with_code(self.db, hackathon_id, student_id, name)
        await self.member_repo.create(
            team_id=team.id, student_id=student_id, joined_at=datetime.now(timezone.utc)
        )
        logger.info("hackathon_team_created", team_id=str(team.id), hackathon_id=str(hackathon_id))
        return team

    async def join_team_by_code(
        self, organization_id: uuid.UUID, hackathon_id: uuid.UUID, student_id: uuid.UUID, code: str
    ) -> TeamMember:
        """Join the team that has this code. A team can only be joined this way, so someone who
        doesn't know the code can't get in. A wrong code gets one generic answer."""
        hackathon = await self._get_registerable_hackathon(hackathon_id, organization_id)

        wanted = normalize_code(code)
        team = None
        if wanted:
            team = (
                await self.db.execute(
                    select(Team)
                    .where(Team.hackathon_id == hackathon_id, Team.join_code == wanted)
                    .with_for_update()
                )
            ).scalar_one_or_none()
        if team is None:
            logger.info("hackathon_team_code_miss", hackathon_id=str(hackathon_id), student_id=str(student_id))
            raise ValidationError("That team code isn't right. Ask a teammate to read it to you again.")
        team_id = team.id

        existing_team = await self.repo.get_for_student_in_hackathon(hackathon_id, student_id)
        if existing_team:
            raise ConflictError("You are already part of a team for this hackathon.")

        member_count = await self.member_repo.count_for_team(team_id)
        if member_count >= hackathon.max_team_size:
            raise ValidationError(f"This team has reached the maximum size of {hackathon.max_team_size}.")

        member = await self.member_repo.create(
            team_id=team_id, student_id=student_id, joined_at=datetime.now(timezone.utc)
        )
        logger.info("hackathon_team_joined", team_id=str(team_id), student_id=str(student_id))
        return member

    async def get_my_team(
        self, hackathon_id: uuid.UUID, student_id: uuid.UUID
    ) -> tuple[Team, list[TeamMember]] | None:
        team = await self.repo.get_for_student_in_hackathon(hackathon_id, student_id)
        if not team:
            return None
        members = await self.member_repo.list_for_team(team.id)
        return team, members

    async def list_teams(self, hackathon_id: uuid.UUID, organization_id: uuid.UUID) -> list[Team]:
        hackathon = await self.hackathon_repo.get_by_id(hackathon_id, organization_id)
        if not hackathon:
            raise NotFoundError("Hackathon", hackathon_id)
        return await self.repo.list_for_hackathon(hackathon_id)

    async def members_by_team(
        self, teams: list[Team], organization_id: uuid.UUID
    ) -> dict[uuid.UUID, list[str]]:
        """Member names per team, for the team lists (one query per team is
        fine at hackathon scale: tens of teams)."""
        names: dict[uuid.UUID, list[str]] = {}
        for team in teams:
            members = await self.member_repo.list_for_team(team.id)
            students = {
                s.id: s.full_name
                for s in await self.student_repo.list_for_ids([m.student_id for m in members], organization_id)
            }
            names[team.id] = [students.get(m.student_id, "Unknown student") for m in members]
        return names
