import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.hackathons.models import Hackathon, HackathonStatus, Submission, Team, TeamMember


class HackathonRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Hackathon:
        hackathon = Hackathon(**fields)
        self.db.add(hackathon)
        await self.db.flush()
        await self.db.refresh(hackathon)
        return hackathon

    async def get_by_id(self, hackathon_id: uuid.UUID, organization_id: uuid.UUID) -> Hackathon | None:
        result = await self.db.execute(
            select(Hackathon).where(
                Hackathon.id == hackathon_id, Hackathon.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> Hackathon | None:
        result = await self.db.execute(
            select(Hackathon).where(
                Hackathon.organization_id == organization_id, Hackathon.code == code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: HackathonStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Hackathon], int]:
        conditions = [Hackathon.organization_id == organization_id]
        if status is not None:
            conditions.append(Hackathon.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(Hackathon).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Hackathon)
            .where(*conditions)
            .order_by(Hackathon.start_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, hackathon: Hackathon, **fields) -> Hackathon:
        for key, value in fields.items():
            if value is not None:
                setattr(hackathon, key, value)
        await self.db.flush()
        await self.db.refresh(hackathon)
        return hackathon

    async def delete(self, hackathon: Hackathon) -> None:
        await self.db.delete(hackathon)
        await self.db.flush()


class TeamRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Team:
        team = Team(**fields)
        self.db.add(team)
        await self.db.flush()
        await self.db.refresh(team)
        return team

    async def get_by_id(self, team_id: uuid.UUID) -> Team | None:
        result = await self.db.execute(select(Team).where(Team.id == team_id))
        return result.scalar_one_or_none()

    async def list_for_hackathon(self, hackathon_id: uuid.UUID) -> list[Team]:
        result = await self.db.execute(
            select(Team).where(Team.hackathon_id == hackathon_id).order_by(Team.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_for_student_in_hackathon(
        self, hackathon_id: uuid.UUID, student_id: uuid.UUID
    ) -> Team | None:
        result = await self.db.execute(
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(Team.hackathon_id == hackathon_id, TeamMember.student_id == student_id)
        )
        return result.scalar_one_or_none()


class TeamMemberRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> TeamMember:
        member = TeamMember(**fields)
        self.db.add(member)
        await self.db.flush()
        await self.db.refresh(member)
        return member

    async def count_for_team(self, team_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(TeamMember).where(TeamMember.team_id == team_id)
        )
        return result.scalar_one()

    async def get(self, team_id: uuid.UUID, student_id: uuid.UUID) -> TeamMember | None:
        result = await self.db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id, TeamMember.student_id == student_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_team(self, team_id: uuid.UUID) -> list[TeamMember]:
        result = await self.db.execute(
            select(TeamMember).where(TeamMember.team_id == team_id).order_by(TeamMember.joined_at.asc())
        )
        return list(result.scalars().all())


class SubmissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Submission:
        submission = Submission(**fields)
        self.db.add(submission)
        await self.db.flush()
        await self.db.refresh(submission)
        return submission

    async def get_by_team(self, team_id: uuid.UUID) -> Submission | None:
        result = await self.db.execute(select(Submission).where(Submission.team_id == team_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, submission_id: uuid.UUID) -> Submission | None:
        result = await self.db.execute(select(Submission).where(Submission.id == submission_id))
        return result.scalar_one_or_none()

    async def list_for_hackathon(self, hackathon_id: uuid.UUID) -> list[Submission]:
        result = await self.db.execute(
            select(Submission)
            .join(Team, Team.id == Submission.team_id)
            .where(Team.hackathon_id == hackathon_id)
            .order_by(Submission.submitted_at.asc())
        )
        return list(result.scalars().all())

    async def update(self, submission: Submission, **fields) -> Submission:
        for key, value in fields.items():
            if value is not None:
                setattr(submission, key, value)
        await self.db.flush()
        await self.db.refresh(submission)
        return submission
