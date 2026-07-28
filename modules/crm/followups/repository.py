import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.crm.followups.models import FollowUp, FollowUpStatus


class FollowUpRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> FollowUp:
        followup = FollowUp(**fields)
        self.db.add(followup)
        await self.db.flush()
        await self.db.refresh(followup)
        return followup

    async def get_by_id(self, followup_id: uuid.UUID) -> FollowUp | None:
        result = await self.db.execute(select(FollowUp).where(FollowUp.id == followup_id))
        return result.scalar_one_or_none()

    async def list_for_lead(self, lead_id: uuid.UUID) -> list[FollowUp]:
        result = await self.db.execute(
            select(FollowUp)
            .where(FollowUp.lead_id == lead_id)
            .order_by(FollowUp.scheduled_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, followup: FollowUp, **fields) -> FollowUp:
        for key, value in fields.items():
            if value is not None:
                setattr(followup, key, value)
        await self.db.flush()
        await self.db.refresh(followup)
        return followup

    async def mark_completed(self, followup: FollowUp, outcome: str, notes: str | None) -> FollowUp:
        followup.status = FollowUpStatus.COMPLETED
        followup.completed_at = datetime.now(timezone.utc)
        followup.outcome = outcome
        if notes:
            followup.notes = notes
        await self.db.flush()
        await self.db.refresh(followup)
        return followup

    async def delete(self, followup: FollowUp) -> None:
        await self.db.delete(followup)
        await self.db.flush()
