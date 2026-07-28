import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.pentrix.challenges.models import Challenge


class ChallengeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Challenge:
        challenge = Challenge(**fields)
        self.db.add(challenge)
        await self.db.flush()
        await self.db.refresh(challenge)
        return challenge

    async def get_by_id(self, challenge_id: uuid.UUID, organization_id: uuid.UUID) -> Challenge | None:
        result = await self.db.execute(
            select(Challenge).where(
                Challenge.id == challenge_id, Challenge.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, category: str | None = None
    ) -> list[Challenge]:
        conditions = [Challenge.organization_id == organization_id]
        if category is not None:
            conditions.append(Challenge.category == category)
        result = await self.db.execute(select(Challenge).where(*conditions))
        return list(result.scalars().all())

    async def update(self, challenge: Challenge, **fields) -> Challenge:
        for key, value in fields.items():
            if value is not None:
                setattr(challenge, key, value)
        await self.db.flush()
        await self.db.refresh(challenge)
        return challenge

    async def delete(self, challenge: Challenge) -> None:
        await self.db.delete(challenge)
        await self.db.flush()
