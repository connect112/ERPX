import uuid
from collections.abc import Collection

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.corporate.projects.models import Project
from modules.corporate.vapt.models import (
    FindingSeverity,
    FindingStatus,
    VAPTEngagement,
    VAPTFinding,
)


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

    async def count_for_organization(self, organization_id: uuid.UUID) -> int:
        """Total engagements across all of an org's projects, in one join query.

        Equivalent to summing ``len(list_for_project(p.id))`` over every project
        the org owns (engagements are scoped to the org only via their project),
        but without the per-project round-trip.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(VAPTEngagement)
            .join(Project, Project.id == VAPTEngagement.project_id)
            .where(Project.organization_id == organization_id)
        )
        return result.scalar_one()

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

    async def severity_breakdown_for_organization(
        self, organization_id: uuid.UUID, open_statuses: Collection[FindingStatus]
    ) -> list[tuple[FindingSeverity, int, int]]:
        """Per-severity (total, open) finding counts across an org's engagements.

        Joins findings → engagements → projects and groups by severity in one
        query, replacing a per-engagement fetch-and-loop. ``open`` counts rows
        whose status is in ``open_statuses`` via a conditional aggregate. Only
        severities that actually occur are returned (callers seed a zero for the
        rest), matching the previous Python accumulation exactly.
        """
        open_count = func.count().filter(VAPTFinding.status.in_(list(open_statuses)))
        result = await self.db.execute(
            select(VAPTFinding.severity, func.count(), open_count)
            .select_from(VAPTFinding)
            .join(VAPTEngagement, VAPTEngagement.id == VAPTFinding.engagement_id)
            .join(Project, Project.id == VAPTEngagement.project_id)
            .where(Project.organization_id == organization_id)
            .group_by(VAPTFinding.severity)
        )
        return [(row[0], int(row[1]), int(row[2])) for row in result.all()]

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
