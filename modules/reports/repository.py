import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.reports.models import ReportExecution, ScheduledReport


class ReportExecutionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> ReportExecution:
        execution = ReportExecution(**fields)
        self.db.add(execution)
        await self.db.flush()
        await self.db.refresh(execution)
        return execution

    async def get_by_id(self, execution_id: uuid.UUID, organization_id: uuid.UUID) -> ReportExecution | None:
        result = await self.db.execute(
            select(ReportExecution).where(
                ReportExecution.id == execution_id, ReportExecution.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        report_key: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ReportExecution], int]:
        conditions = [ReportExecution.organization_id == organization_id]
        if report_key is not None:
            conditions.append(ReportExecution.report_key == report_key)

        count_result = await self.db.execute(select(func.count()).select_from(ReportExecution).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(ReportExecution).where(*conditions).order_by(ReportExecution.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total


class ScheduledReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> ScheduledReport:
        scheduled = ScheduledReport(**fields)
        self.db.add(scheduled)
        await self.db.flush()
        await self.db.refresh(scheduled)
        return scheduled

    async def get_by_id(self, scheduled_report_id: uuid.UUID, organization_id: uuid.UUID) -> ScheduledReport | None:
        result = await self.db.execute(
            select(ScheduledReport).where(
                ScheduledReport.id == scheduled_report_id, ScheduledReport.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None, skip: int = 0, limit: int = 50
    ) -> tuple[list[ScheduledReport], int]:
        conditions = [ScheduledReport.organization_id == organization_id]
        if is_active is not None:
            conditions.append(ScheduledReport.is_active == is_active)

        count_result = await self.db.execute(select(func.count()).select_from(ScheduledReport).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(ScheduledReport).where(*conditions).order_by(ScheduledReport.next_run_at.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_due(self, as_of: datetime) -> list[ScheduledReport]:
        result = await self.db.execute(
            select(ScheduledReport).where(
                ScheduledReport.is_active.is_(True), ScheduledReport.next_run_at <= as_of
            )
        )
        return list(result.scalars().all())

    async def update(self, scheduled: ScheduledReport, **fields) -> ScheduledReport:
        for key, value in fields.items():
            if value is not None:
                setattr(scheduled, key, value)
        await self.db.flush()
        await self.db.refresh(scheduled)
        return scheduled
