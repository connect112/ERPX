import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.hackathons.models import Hackathon, HackathonStatus, Submission, Team, TeamMember
from modules.hackathons.repository import (
    HackathonRepository,
    SubmissionRepository,
    TeamMemberRepository,
    TeamRepository,
)
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

        team = await self.repo.create(
            hackathon_id=hackathon_id, created_by_student_id=student_id, name=name
        )
        await self.member_repo.create(
            team_id=team.id, student_id=student_id, joined_at=datetime.now(timezone.utc)
        )
        logger.info("hackathon_team_created", team_id=str(team.id), hackathon_id=str(hackathon_id))
        return team

    async def join_team(
        self, organization_id: uuid.UUID, hackathon_id: uuid.UUID, team_id: uuid.UUID, student_id: uuid.UUID
    ) -> TeamMember:
        hackathon = await self._get_registerable_hackathon(hackathon_id, organization_id)

        team = await self.repo.get_by_id(team_id)
        if not team or team.hackathon_id != hackathon_id:
            raise NotFoundError("Team", team_id)

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


class SubmissionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SubmissionRepository(db)
        self.team_repo = TeamRepository(db)
        self.member_repo = TeamMemberRepository(db)
        self.hackathon_repo = HackathonRepository(db)

    async def submit_project(
        self,
        organization_id: uuid.UUID,
        hackathon_id: uuid.UUID,
        team_id: uuid.UUID,
        student_id: uuid.UUID,
        title: str,
        description: str | None,
        repo_url: str | None,
        demo_url: str | None,
    ) -> Submission:
        hackathon = await self.hackathon_repo.get_by_id(hackathon_id, organization_id)
        if not hackathon:
            raise NotFoundError("Hackathon", hackathon_id)
        if hackathon.status not in (HackathonStatus.REGISTRATION_OPEN, HackathonStatus.ONGOING):
            raise ValidationError("This hackathon is not currently accepting submissions.")

        team = await self.team_repo.get_by_id(team_id)
        if not team or team.hackathon_id != hackathon_id:
            raise NotFoundError("Team", team_id)
        member = await self.member_repo.get(team_id, student_id)
        if not member:
            raise ValidationError("You are not a member of this team.")

        existing = await self.repo.get_by_team(team_id)
        if existing:
            updated = await self.repo.update(
                existing,
                title=title,
                description=description,
                repo_url=repo_url,
                demo_url=demo_url,
                submitted_at=datetime.now(timezone.utc),
            )
            logger.info("hackathon_submission_updated", submission_id=str(updated.id))
            return updated

        submission = await self.repo.create(
            team_id=team_id,
            title=title,
            description=description,
            repo_url=repo_url,
            demo_url=demo_url,
            submitted_at=datetime.now(timezone.utc),
        )
        logger.info("hackathon_submission_created", submission_id=str(submission.id))
        return submission

    async def get_for_team(self, team_id: uuid.UUID) -> Submission | None:
        return await self.repo.get_by_team(team_id)

    async def list_for_hackathon(self, hackathon_id: uuid.UUID, organization_id: uuid.UUID) -> list[Submission]:
        hackathon = await self.hackathon_repo.get_by_id(hackathon_id, organization_id)
        if not hackathon:
            raise NotFoundError("Hackathon", hackathon_id)
        return await self.repo.list_for_hackathon(hackathon_id)

    async def grade_submission(
        self, submission_id: uuid.UUID, organization_id: uuid.UUID, score: int, feedback: str | None
    ) -> Submission:
        submission = await self.repo.get_by_id(submission_id)
        if not submission:
            raise NotFoundError("Submission", submission_id)
        team = await self.team_repo.get_by_id(submission.team_id)
        if not team:
            raise NotFoundError("Team", submission.team_id)
        hackathon = await self.hackathon_repo.get_by_id(team.hackathon_id, organization_id)
        if not hackathon:
            raise NotFoundError("Hackathon", team.hackathon_id)

        updated = await self.repo.update(submission, score=score, feedback=feedback)
        logger.info("hackathon_submission_graded", submission_id=str(submission_id), score=score)
        return updated
