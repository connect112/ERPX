import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.communication.models import CommunicationChannel, CommunicationLog, CommunicationStatus


class CommunicationLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> CommunicationLog:
        log = CommunicationLog(**fields)
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)
        return log

    async def get_by_id(self, log_id: uuid.UUID, organization_id: uuid.UUID) -> CommunicationLog | None:
        result = await self.db.execute(
            select(CommunicationLog).where(
                CommunicationLog.id == log_id, CommunicationLog.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        channel: CommunicationChannel | None = None,
        status: CommunicationStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CommunicationLog], int]:
        conditions = [CommunicationLog.organization_id == organization_id]
        if channel is not None:
            conditions.append(CommunicationLog.channel == channel)
        if status is not None:
            conditions.append(CommunicationLog.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(CommunicationLog).where(*conditions)
        )
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(CommunicationLog)
            .where(*conditions)
            .order_by(CommunicationLog.sent_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total
