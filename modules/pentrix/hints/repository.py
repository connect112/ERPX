import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.pentrix.hints.models import Hint, HintUnlock


class HintRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Hint:
        hint = Hint(**fields)
        self.db.add(hint)
        await self.db.flush()
        await self.db.refresh(hint)
        return hint

    async def get_by_id(self, hint_id: uuid.UUID) -> Hint | None:
        result = await self.db.execute(select(Hint).where(Hint.id == hint_id))
        return result.scalar_one_or_none()

    async def list_for_challenge(self, challenge_id: uuid.UUID) -> list[Hint]:
        result = await self.db.execute(
            select(Hint).where(Hint.challenge_id == challenge_id).order_by(Hint.order_index)
        )
        return list(result.scalars().all())

    async def get_unlock(self, student_id: uuid.UUID, hint_id: uuid.UUID) -> HintUnlock | None:
        result = await self.db.execute(
            select(HintUnlock).where(
                HintUnlock.student_id == student_id, HintUnlock.hint_id == hint_id
            )
        )
        return result.scalar_one_or_none()

    async def unlock(self, student_id: uuid.UUID, hint_id: uuid.UUID) -> HintUnlock:
        unlock = HintUnlock(student_id=student_id, hint_id=hint_id)
        self.db.add(unlock)
        await self.db.flush()
        await self.db.refresh(unlock)
        return unlock

    async def list_unlocked_hint_ids(self, student_id: uuid.UUID, challenge_id: uuid.UUID) -> set[uuid.UUID]:
        result = await self.db.execute(
            select(HintUnlock.hint_id)
            .join(Hint, Hint.id == HintUnlock.hint_id)
            .where(HintUnlock.student_id == student_id, Hint.challenge_id == challenge_id)
        )
        return set(result.scalars().all())
