import uuid
from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.leave.models import LeaveApplication, LeaveApplicationStatus, LeaveType


class LeaveTypeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> LeaveType:
        leave_type = LeaveType(**fields)
        self.db.add(leave_type)
        await self.db.flush()
        await self.db.refresh(leave_type)
        return leave_type

    async def get_by_id(self, leave_type_id: uuid.UUID, organization_id: uuid.UUID) -> LeaveType | None:
        result = await self.db.execute(
            select(LeaveType).where(
                LeaveType.id == leave_type_id, LeaveType.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> LeaveType | None:
        result = await self.db.execute(
            select(LeaveType).where(LeaveType.organization_id == organization_id, LeaveType.code == code)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[LeaveType]:
        conditions = [LeaveType.organization_id == organization_id]
        if is_active is not None:
            conditions.append(LeaveType.is_active == is_active)
        result = await self.db.execute(select(LeaveType).where(*conditions).order_by(LeaveType.name.asc()))
        return list(result.scalars().all())

    async def update(self, leave_type: LeaveType, **fields) -> LeaveType:
        for key, value in fields.items():
            if value is not None:
                setattr(leave_type, key, value)
        await self.db.flush()
        await self.db.refresh(leave_type)
        return leave_type


class LeaveApplicationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> LeaveApplication:
        application = LeaveApplication(**fields)
        self.db.add(application)
        await self.db.flush()
        await self.db.refresh(application)
        return application

    async def get_by_id(self, application_id: uuid.UUID, organization_id: uuid.UUID) -> LeaveApplication | None:
        result = await self.db.execute(
            select(LeaveApplication).where(
                LeaveApplication.id == application_id, LeaveApplication.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_employee(
        self,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID | None = None,
        status: LeaveApplicationStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[LeaveApplication], int]:
        conditions = [LeaveApplication.employee_id == employee_id]
        if leave_type_id is not None:
            conditions.append(LeaveApplication.leave_type_id == leave_type_id)
        if status is not None:
            conditions.append(LeaveApplication.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(LeaveApplication).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(LeaveApplication)
            .where(*conditions)
            .order_by(LeaveApplication.start_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: LeaveApplicationStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[LeaveApplication], int]:
        conditions = [LeaveApplication.organization_id == organization_id]
        if status is not None:
            conditions.append(LeaveApplication.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(LeaveApplication).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(LeaveApplication)
            .where(*conditions)
            .order_by(LeaveApplication.start_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def find_overlapping(
        self, employee_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[LeaveApplication]:
        result = await self.db.execute(
            select(LeaveApplication).where(
                LeaveApplication.employee_id == employee_id,
                LeaveApplication.status.in_(
                    [LeaveApplicationStatus.PENDING, LeaveApplicationStatus.APPROVED]
                ),
                LeaveApplication.start_date <= end_date,
                LeaveApplication.end_date >= start_date,
            )
        )
        return list(result.scalars().all())

    async def sum_days_for_year(
        self, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int, statuses: list[LeaveApplicationStatus]
    ) -> float:
        result = await self.db.execute(
            select(func.coalesce(func.sum(LeaveApplication.number_of_days), 0)).where(
                LeaveApplication.employee_id == employee_id,
                LeaveApplication.leave_type_id == leave_type_id,
                LeaveApplication.status.in_(statuses),
                func.extract("year", LeaveApplication.start_date) == year,
            )
        )
        return float(result.scalar_one())

    async def update(self, application: LeaveApplication, **fields) -> LeaveApplication:
        for key, value in fields.items():
            if value is not None:
                setattr(application, key, value)
        await self.db.flush()
        await self.db.refresh(application)
        return application
