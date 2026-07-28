import uuid
from datetime import date

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.attendance.models import AttendanceRecord, AttendanceStatus


class AttendanceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AttendanceRecord:
        record = AttendanceRecord(**fields)
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_by_id(self, record_id: uuid.UUID, organization_id: uuid.UUID) -> AttendanceRecord | None:
        result = await self.db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.id == record_id, AttendanceRecord.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_for_employee_date(
        self, employee_id: uuid.UUID, attendance_date: date
    ) -> AttendanceRecord | None:
        result = await self.db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == employee_id,
                AttendanceRecord.attendance_date == attendance_date,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_employee(
        self,
        employee_id: uuid.UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AttendanceRecord], int]:
        conditions = [AttendanceRecord.employee_id == employee_id]
        if date_from is not None:
            conditions.append(AttendanceRecord.attendance_date >= date_from)
        if date_to is not None:
            conditions.append(AttendanceRecord.attendance_date <= date_to)

        count_result = await self.db.execute(
            select(func.count()).select_from(AttendanceRecord).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(AttendanceRecord)
            .where(*conditions)
            .order_by(AttendanceRecord.attendance_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        attendance_date: date | None = None,
        status: AttendanceStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AttendanceRecord], int]:
        conditions = [AttendanceRecord.organization_id == organization_id]
        if branch_id is not None:
            conditions.append(AttendanceRecord.branch_id == branch_id)
        if attendance_date is not None:
            conditions.append(AttendanceRecord.attendance_date == attendance_date)
        if status is not None:
            conditions.append(AttendanceRecord.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(AttendanceRecord).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(AttendanceRecord)
            .where(*conditions)
            .order_by(AttendanceRecord.attendance_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def monthly_summary(self, employee_id: uuid.UUID, year: int, month: int) -> list[AttendanceRecord]:
        result = await self.db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == employee_id,
                extract("year", AttendanceRecord.attendance_date) == year,
                extract("month", AttendanceRecord.attendance_date) == month,
            )
        )
        return list(result.scalars().all())

    async def update(self, record: AttendanceRecord, **fields) -> AttendanceRecord:
        for key, value in fields.items():
            if value is not None:
                setattr(record, key, value)
        await self.db.flush()
        await self.db.refresh(record)
        return record
