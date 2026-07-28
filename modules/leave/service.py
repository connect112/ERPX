import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.attendance.models import AttendanceStatus
from modules.attendance.service import AttendanceService
from modules.employees.repository import EmployeeRepository
from modules.leave.models import LeaveApplication, LeaveApplicationStatus, LeaveType
from modules.leave.repository import LeaveApplicationRepository, LeaveTypeRepository

logger = get_logger(__name__)

_OPEN_STATUSES = [LeaveApplicationStatus.PENDING, LeaveApplicationStatus.APPROVED]


class LeaveTypeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LeaveTypeRepository(db)

    async def create_leave_type(self, organization_id: uuid.UUID, code: str, **fields) -> LeaveType:
        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"A leave type with code '{code}' already exists.")
        leave_type = await self.repo.create(organization_id=organization_id, code=code, **fields)
        logger.info("leave_type_created", leave_type_id=str(leave_type.id))
        return leave_type

    async def get_leave_type(self, leave_type_id: uuid.UUID, organization_id: uuid.UUID) -> LeaveType:
        leave_type = await self.repo.get_by_id(leave_type_id, organization_id)
        if not leave_type:
            raise NotFoundError("Leave type", leave_type_id)
        return leave_type

    async def list_leave_types(self, organization_id: uuid.UUID, is_active: bool | None = None) -> list[LeaveType]:
        return await self.repo.list_for_organization(organization_id, is_active)

    async def update_leave_type(
        self, leave_type_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> LeaveType:
        leave_type = await self.get_leave_type(leave_type_id, organization_id)
        updated = await self.repo.update(leave_type, **fields)
        logger.info("leave_type_updated", leave_type_id=str(leave_type_id))
        return updated


class LeaveApplicationService:
    """
    Leave balances are never stored — `get_balance` derives them from
    `LeaveType.annual_quota` minus approved/pending `LeaveApplication`
    days for the year, so they can't drift out of sync with the
    applications themselves. Approving a leave marks every calendar day
    in its range as ON_LEAVE in Attendance; this does not yet account for
    an employee's weekly-off/shift schedule (no roster module exists
    yet), so a week off inside an approved leave range is currently
    recorded as an ON_LEAVE attendance day rather than WEEK_OFF.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LeaveApplicationRepository(db)
        self.leave_type_repo = LeaveTypeRepository(db)
        self.employee_repo = EmployeeRepository(db)
        self.attendance_service = AttendanceService(db)

    async def get_balance(
        self, employee_id: uuid.UUID, organization_id: uuid.UUID, leave_type_id: uuid.UUID, year: int
    ) -> dict:
        employee = await self.employee_repo.get_by_id(employee_id, organization_id)
        if not employee:
            raise NotFoundError("Employee", employee_id)
        leave_type = await self.leave_type_repo.get_by_id(leave_type_id, organization_id)
        if not leave_type:
            raise NotFoundError("Leave type", leave_type_id)

        days_used = await self.repo.sum_days_for_year(
            employee_id, leave_type_id, year, [LeaveApplicationStatus.APPROVED]
        )
        days_pending = await self.repo.sum_days_for_year(
            employee_id, leave_type_id, year, [LeaveApplicationStatus.PENDING]
        )
        return {
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "leave_type_name": leave_type.name,
            "year": year,
            "annual_quota": float(leave_type.annual_quota),
            "days_used": days_used,
            "days_pending": days_pending,
            "balance": round(float(leave_type.annual_quota) - days_used - days_pending, 2),
        }

    async def list_balances_for_employee(
        self, employee_id: uuid.UUID, organization_id: uuid.UUID, year: int
    ) -> list[dict]:
        leave_types = await self.leave_type_repo.list_for_organization(organization_id, is_active=True)
        return [
            await self.get_balance(employee_id, organization_id, lt.id, year) for lt in leave_types
        ]

    async def apply_leave(
        self,
        organization_id: uuid.UUID,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID,
        start_date: date,
        end_date: date,
        reason: str,
    ) -> LeaveApplication:
        employee = await self.employee_repo.get_by_id(employee_id, organization_id)
        if not employee:
            raise NotFoundError("Employee", employee_id)
        leave_type = await self.leave_type_repo.get_by_id(leave_type_id, organization_id)
        if not leave_type:
            raise NotFoundError("Leave type", leave_type_id)
        if not leave_type.is_active:
            raise ValidationError("This leave type is not currently active.")
        if end_date < start_date:
            raise ValidationError("End date cannot be before start date.")

        overlapping = await self.repo.find_overlapping(employee_id, start_date, end_date)
        if overlapping:
            raise ConflictError("This employee already has a pending or approved leave overlapping these dates.")

        number_of_days = (end_date - start_date).days + 1

        balance = await self.get_balance(employee_id, organization_id, leave_type_id, start_date.year)
        if number_of_days > balance["balance"]:
            raise ValidationError(
                f"Insufficient leave balance: requested {number_of_days} day(s), "
                f"only {balance['balance']} day(s) available for '{leave_type.name}'."
            )

        application = await self.repo.create(
            organization_id=organization_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            number_of_days=number_of_days,
            reason=reason,
        )
        logger.info("leave_applied", application_id=str(application.id), employee_id=str(employee_id))
        return application

    async def get_application(self, application_id: uuid.UUID, organization_id: uuid.UUID) -> LeaveApplication:
        application = await self.repo.get_by_id(application_id, organization_id)
        if not application:
            raise NotFoundError("Leave application", application_id)
        return application

    async def list_for_employee(self, employee_id: uuid.UUID, organization_id: uuid.UUID, **filters):
        employee = await self.employee_repo.get_by_id(employee_id, organization_id)
        if not employee:
            raise NotFoundError("Employee", employee_id)
        return await self.repo.list_for_employee(employee_id, **filters)

    async def list_for_organization(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def approve_leave(
        self, application_id: uuid.UUID, organization_id: uuid.UUID, approved_by_user_id: uuid.UUID
    ) -> LeaveApplication:
        application = await self.get_application(application_id, organization_id)
        if application.status != LeaveApplicationStatus.PENDING:
            raise ValidationError(
                f"Only pending leave applications can be approved (this one is '{application.status.value}')."
            )

        leave_type = await self.leave_type_repo.get_by_id(application.leave_type_id, organization_id)

        current = application.start_date
        while current <= application.end_date:
            await self.attendance_service.mark_attendance(
                organization_id,
                application.employee_id,
                current,
                AttendanceStatus.ON_LEAVE,
                remarks=f"Approved leave: {leave_type.name if leave_type else 'N/A'}",
            )
            current += timedelta(days=1)

        updated = await self.repo.update(
            application,
            status=LeaveApplicationStatus.APPROVED,
            approved_by_user_id=approved_by_user_id,
            approved_at=datetime.now(timezone.utc),
        )
        logger.info("leave_approved", application_id=str(application_id))
        return updated

    async def reject_leave(
        self, application_id: uuid.UUID, organization_id: uuid.UUID, rejection_reason: str
    ) -> LeaveApplication:
        application = await self.get_application(application_id, organization_id)
        if application.status != LeaveApplicationStatus.PENDING:
            raise ValidationError("Only pending leave applications can be rejected.")
        updated = await self.repo.update(
            application, status=LeaveApplicationStatus.REJECTED, rejection_reason=rejection_reason
        )
        logger.info("leave_rejected", application_id=str(application_id))
        return updated

    async def cancel_leave(self, application_id: uuid.UUID, organization_id: uuid.UUID) -> LeaveApplication:
        application = await self.get_application(application_id, organization_id)
        if application.status != LeaveApplicationStatus.PENDING:
            raise ValidationError(
                "Only pending leave applications can be cancelled. "
                "An already-approved leave must be rejected by an approver instead."
            )
        updated = await self.repo.update(application, status=LeaveApplicationStatus.CANCELLED)
        logger.info("leave_cancelled", application_id=str(application_id))
        return updated
