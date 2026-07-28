import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.corporate.vapt.models import FindingStatus, VAPTEngagement, VAPTFinding


class VAPTEngagementRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> VAPTEngagement:
        engagement = VAPTEngagement(**fields)
        self.db.add(engagement)
        await self.db.flush()
        await self.db.refresh(engagement)
        return engagement

    async def get_by_id(self, engagement_id: uuid.UUID) -> VAPTEngagement | None:
        result = await self.db.execute(select(VAPTEngagement).where(VAPTEngagement.id == engagement_id))
        return result.scalar_one_or_none()

    async def list_for_project(self, project_id: uuid.UUID) -> list[VAPTEngagement]:
        result = await self.db.execute(
            select(VAPTEngagement)
            .where(VAPTEngagement.project_id == project_id)
            .order_by(VAPTEngagement.start_date.desc())
        )
        return list(result.scalars().all())

    async def update(self, engagement: VAPTEngagement, **fields) -> VAPTEngagement:
        for key, value in fields.items():
            if value is not None:
                setattr(engagement, key, value)
        await self.db.flush()
        await self.db.refresh(engagement)
        return engagement


class VAPTFindingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> VAPTFinding:
        finding = VAPTFinding(**fields)
        self.db.add(finding)
        await self.db.flush()
        await self.db.refresh(finding)
        return finding

    async def get_by_id(self, finding_id: uuid.UUID) -> VAPTFinding | None:
        result = await self.db.execute(select(VAPTFinding).where(VAPTFinding.id == finding_id))
        return result.scalar_one_or_none()

    async def list_for_engagement(
        self, engagement_id: uuid.UUID, status: FindingStatus | None = None
    ) -> list[VAPTFinding]:
        conditions = [VAPTFinding.engagement_id == engagement_id]
        if status is not None:
            conditions.append(VAPTFinding.status == status)
        result = await self.db.execute(
            select(VAPTFinding).where(*conditions).order_by(VAPTFinding.reported_date.desc())
        )
        return list(result.scalars().all())

    async def update(self, finding: VAPTFinding, **fields) -> VAPTFinding:
        for key, value in fields.items():
            if value is not None:
                setattr(finding, key, value)
        await self.db.flush()
        await self.db.refresh(finding)
        return finding
