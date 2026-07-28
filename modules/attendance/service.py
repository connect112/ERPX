import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.attendance.models import AttendanceRecord, AttendanceStatus
from modules.attendance.repository import AttendanceRepository
from modules.employees.repository import EmployeeRepository

logger = get_logger(__name__)

# Below this many worked hours in a day, a punched-in/out record is
# treated as a half day rather than a full present day. Configurable per
# deployment in a later settings pass; kept as a module constant for now.
FULL_DAY_MIN_HOURS = 4.0


def _work_hours(check_in: datetime, check_out: datetime) -> float:
    delta = check_out - check_in
    return round(delta.total_seconds() / 3600, 2)


class AttendanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AttendanceRepository(db)
        self.employee_repo = EmployeeRepository(db)

    async def _get_employee_or_raise(self, employee_id: uuid.UUID, organization_id: uuid.UUID):
        employee = await self.employee_repo.get_by_id(employee_id, organization_id)
        if not employee:
            raise NotFoundError("Employee", employee_id)
        return employee

    async def check_in(
        self, organization_id: uuid.UUID, employee_id: uuid.UUID, check_in_time: datetime | None
    ) -> AttendanceRecord:
        employee = await self._get_employee_or_raise(employee_id, organization_id)
        timestamp = check_in_time or datetime.now(timezone.utc)
        today = timestamp.date()

        existing = await self.repo.get_for_employee_date(employee_id, today)
        if existing is not None:
            if existing.check_in_time is not None:
                raise ValidationError("This employee has already checked in today.")
            updated = await self.repo.update(existing, check_in_time=timestamp, status=AttendanceStatus.PRESENT)
            return updated

        record = await self.repo.create(
            organization_id=organization_id,
            branch_id=employee.branch_id,
            employee_id=employee_id,
            attendance_date=today,
            check_in_time=timestamp,
            status=AttendanceStatus.PRESENT,
        )
        logger.info("employee_checked_in", employee_id=str(employee_id), record_id=str(record.id))
        return record

    async def check_out(
        self, organization_id: uuid.UUID, employee_id: uuid.UUID, check_out_time: datetime | None
    ) -> AttendanceRecord:
        await self._get_employee_or_raise(employee_id, organization_id)
        timestamp = check_out_time or datetime.now(timezone.utc)
        today = timestamp.date()

        record = await self.repo.get_for_employee_date(employee_id, today)
        if record is None or record.check_in_time is None:
            raise ValidationError("This employee has not checked in today.")
        if record.check_out_time is not None:
            raise ValidationError("This employee has already checked out today.")
        if timestamp <= record.check_in_time:
            raise ValidationError("Check-out time must be after check-in time.")

        hours = _work_hours(record.check_in_time, timestamp)
        status = AttendanceStatus.PRESENT if hours >= FULL_DAY_MIN_HOURS else AttendanceStatus.HALF_DAY
        updated = await self.repo.update(record, check_out_time=timestamp, work_hours=hours, status=status)
        logger.info("employee_checked_out", employee_id=str(employee_id), work_hours=hours)
        return updated

    async def mark_attendance(
        self,
        organization_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
        status: AttendanceStatus,
        remarks: str | None = None,
    ) -> AttendanceRecord:
        employee = await self._get_employee_or_raise(employee_id, organization_id)
        existing = await self.repo.get_for_employee_date(employee_id, attendance_date)
        if existing is not None:
            updated = await self.repo.update(existing, status=status, remarks=remarks)
            return updated

        record = await self.repo.create(
            organization_id=organization_id,
            branch_id=employee.branch_id,
            employee_id=employee_id,
            attendance_date=attendance_date,
            status=status,
            remarks=remarks,
        )
        logger.info("attendance_marked", employee_id=str(employee_id), status=status.value)
        return record

    async def get_record(self, record_id: uuid.UUID, organization_id: uuid.UUID) -> AttendanceRecord:
        record = await self.repo.get_by_id(record_id, organization_id)
        if not record:
            raise NotFoundError("Attendance record", record_id)
        return record

    async def regularize(
        self,
        record_id: uuid.UUID,
        organization_id: uuid.UUID,
        regularization_reason: str,
        check_in_time: datetime | None = None,
        check_out_time: datetime | None = None,
        status: AttendanceStatus | None = None,
    ) -> AttendanceRecord:
        record = await self.get_record(record_id, organization_id)

        new_check_in = check_in_time or record.check_in_time
        new_check_out = check_out_time or record.check_out_time
        new_status = status

        work_hours = record.work_hours
        if new_check_in and new_check_out:
            if new_check_out <= new_check_in:
                raise ValidationError("Check-out time must be after check-in time.")
            work_hours = _work_hours(new_check_in, new_check_out)
            if new_status is None:
                new_status = (
                    AttendanceStatus.PRESENT if work_hours >= FULL_DAY_MIN_HOURS else AttendanceStatus.HALF_DAY
                )

        updated = await self.repo.update(
            record,
            check_in_time=new_check_in,
            check_out_time=new_check_out,
            work_hours=work_hours,
            status=new_status,
            is_regularized=True,
            regularization_reason=regularization_reason,
        )
        logger.info("attendance_regularized", record_id=str(record_id))
        return updated

    async def list_for_employee(self, employee_id: uuid.UUID, organization_id: uuid.UUID, **filters):
        await self._get_employee_or_raise(employee_id, organization_id)
        return await self.repo.list_for_employee(employee_id, **filters)

    async def list_for_organization(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def monthly_summary(self, employee_id: uuid.UUID, organization_id: uuid.UUID, year: int, month: int) -> dict:
        await self._get_employee_or_raise(employee_id, organization_id)
        records = await self.repo.monthly_summary(employee_id, year, month)

        counts = {status: 0 for status in AttendanceStatus}
        total_hours = 0.0
        for record in records:
            counts[record.status] += 1
            if record.work_hours:
                total_hours += float(record.work_hours)

        return {
            "employee_id": employee_id,
            "year": year,
            "month": month,
            "present_days": counts[AttendanceStatus.PRESENT],
            "absent_days": counts[AttendanceStatus.ABSENT],
            "half_days": counts[AttendanceStatus.HALF_DAY],
            "leave_days": counts[AttendanceStatus.ON_LEAVE],
            "holiday_days": counts[AttendanceStatus.HOLIDAY],
            "week_off_days": counts[AttendanceStatus.WEEK_OFF],
            "total_work_hours": round(total_hours, 2),
        }
