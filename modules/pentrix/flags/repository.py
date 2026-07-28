import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.pentrix.flags.models import Flag, Submission


class FlagRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_challenge(self, challenge_id: uuid.UUID) -> Flag | None:
        result = await self.db.execute(select(Flag).where(Flag.challenge_id == challenge_id))
        return result.scalar_one_or_none()

    async def upsert(self, challenge_id: uuid.UUID, flag_hash: str) -> Flag:
        existing = await self.get_by_challenge(challenge_id)
        if existing:
            existing.flag_hash = flag_hash
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        flag = Flag(challenge_id=challenge_id, flag_hash=flag_hash)
        self.db.add(flag)
        await self.db.flush()
        await self.db.refresh(flag)
        return flag


class SubmissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, challenge_id: uuid.UUID, student_id: uuid.UUID) -> Submission | None:
        result = await self.db.execute(
            select(Submission).where(
                Submission.challenge_id == challenge_id, Submission.student_id == student_id
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **fields) -> Submission:
        submission = Submission(**fields)
        self.db.add(submission)
        await self.db.flush()
        await self.db.refresh(submission)
        return submission

    async def list_for_student(self, student_id: uuid.UUID) -> list[Submission]:
        result = await self.db.execute(select(Submission).where(Submission.student_id == student_id))
        return list(result.scalars().all())

    async def list_for_organization_solves(self, student_ids: list[uuid.UUID]) -> list[Submission]:
        if not student_ids:
            return []
        result = await self.db.execute(
            select(Submission).where(Submission.student_id.in_(student_ids))
        )
        return list(result.scalars().all())
