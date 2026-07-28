import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.crm.counselling.models import CounsellingSession, CounsellingStatus


class CounsellingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> CounsellingSession:
        session = CounsellingSession(**fields)
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> CounsellingSession | None:
        result = await self.db.execute(
            select(CounsellingSession).where(CounsellingSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def list_for_lead(self, lead_id: uuid.UUID) -> list[CounsellingSession]:
        result = await self.db.execute(
            select(CounsellingSession)
            .where(CounsellingSession.lead_id == lead_id)
            .order_by(CounsellingSession.scheduled_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, session: CounsellingSession, **fields) -> CounsellingSession:
        for key, value in fields.items():
            if value is not None:
                setattr(session, key, value)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def mark_completed(
        self, session: CounsellingSession, recommended_course: str | None, notes: str | None
    ) -> CounsellingSession:
        session.status = CounsellingStatus.COMPLETED
        if recommended_course:
            session.recommended_course = recommended_course
        if notes:
            session.notes = notes
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def delete(self, session: CounsellingSession) -> None:
        await self.db.delete(session)
        await self.db.flush()
