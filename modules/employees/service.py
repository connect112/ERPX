import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.core.security import hash_password
from modules.authentication.models import UserStatus
from modules.authentication.repository import AuthRepository
from modules.authentication.tasks import send_password_reset_email_task
from modules.employees.models import Employee, EmploymentStatus
from modules.employees.repository import EmployeeRepository
from modules.hr.repository import DepartmentRepository, DesignationRepository
from modules.users.repository import UserProfileRepository

logger = get_logger(__name__)

_EXIT_STATUSES = {EmploymentStatus.RESIGNED, EmploymentStatus.TERMINATED, EmploymentStatus.RETIRED}

# A first login shouldn't expire before the invited employee has opened
# the email — mirrors modules/provisioning/service.py's identical
# SET_PASSWORD_TOKEN_TTL_HOURS for the same reason.
_INVITE_TOKEN_TTL_HOURS = 72


class EmployeeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = EmployeeRepository(db)
        self.department_repo = DepartmentRepository(db)
        self.designation_repo = DesignationRepository(db)
        self.auth_repo = AuthRepository(db)
        self.profile_repo = UserProfileRepository(db)

    async def _validate_org_refs(
        self,
        organization_id: uuid.UUID,
        department_id: uuid.UUID | None,
        designation_id: uuid.UUID | None,
        reporting_manager_id: uuid.UUID | None,
        employee_id: uuid.UUID | None = None,
    ) -> None:
        if department_id is not None:
            department = await self.department_repo.get_by_id(department_id, organization_id)
            if not department:
                raise NotFoundError("Department", department_id)
        if designation_id is not None:
            designation = await self.designation_repo.get_by_id(designation_id, organization_id)
            if not designation:
                raise NotFoundError("Designation", designation_id)
        if reporting_manager_id is not None:
            if reporting_manager_id == employee_id:
                raise ValidationError("An employee cannot report to themselves.")
            manager = await self.repo.get_by_id(reporting_manager_id, organization_id)
            if not manager:
                raise NotFoundError("Reporting manager", reporting_manager_id)

    async def create_employee(
        self, organization_id: uuid.UUID, employee_code: str, **fields
    ) -> Employee:
        existing = await self.repo.get_by_code(organization_id, employee_code)
        if existing:
            raise ConflictError(f"An employee with code '{employee_code}' already exists.")

        await self._validate_org_refs(
            organization_id,
            fields.get("department_id"),
            fields.get("designation_id"),
            fields.get("reporting_manager_id"),
        )

        employee = await self.repo.create(
            organization_id=organization_id, employee_code=employee_code, **fields
        )
        logger.info("employee_created", employee_id=str(employee.id), employee_code=employee_code)
        return employee

    async def get_employee(self, employee_id: uuid.UUID, organization_id: uuid.UUID) -> Employee:
        employee = await self.repo.get_by_id(employee_id, organization_id)
        if not employee:
            raise NotFoundError("Employee", employee_id)
        return employee

    async def list_employees(self, organization_id: uuid.UUID, **filters) -> tuple[list[Employee], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def list_direct_reports(self, manager_id: uuid.UUID, organization_id: uuid.UUID) -> list[Employee]:
        await self.get_employee(manager_id, organization_id)
        return await self.repo.list_direct_reports(manager_id)

    async def update_employee(
        self, employee_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Employee:
        employee = await self.get_employee(employee_id, organization_id)
        await self._validate_org_refs(
            organization_id,
            fields.get("department_id"),
            fields.get("designation_id"),
            fields.get("reporting_manager_id"),
            employee_id=employee_id,
        )
        updated = await self.repo.update(employee, **fields)
        logger.info("employee_updated", employee_id=str(employee_id))
        return updated

    async def change_status(
        self,
        employee_id: uuid.UUID,
        organization_id: uuid.UUID,
        employment_status: EmploymentStatus,
        date_of_exit,
    ) -> Employee:
        employee = await self.get_employee(employee_id, organization_id)
        if employment_status in _EXIT_STATUSES and date_of_exit is None:
            raise ValidationError(
                f"A date of exit is required when marking an employee as '{employment_status.value}'."
            )
        updated = await self.repo.update(
            employee, employment_status=employment_status, date_of_exit=date_of_exit
        )
        logger.info("employee_status_changed", employee_id=str(employee_id), status=employment_status.value)
        return updated

    async def delete_employee(self, employee_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        employee = await self.get_employee(employee_id, organization_id)
        await self.repo.soft_delete(employee)
        logger.info("employee_deleted", employee_id=str(employee_id))

    async def invite_employee(self, employee_id: uuid.UUID, organization_id: uuid.UUID) -> Employee:
        """
        Create the employee-portal login for an existing HR record — the
        Employee row on its own has never had a way to get one (unlike
        Student, which modules.provisioning always creates alongside a
        User). Mirrors provisioning's own account-creation shape: a
        random, never-returned password, and a "set your password" email
        via the same generic token machinery auth's own forgot-password
        flow uses — no separate "welcome" token type invented for this.

        No role is assigned: every employee-portal "me" endpoint is
        ownership-gated the same way students' are (see
        modules/employees/dependencies.py), so none is needed for
        self-service to work — matching how modules/authorization/
        service.py explains it deliberately leaves several other
        ownership-covered permissions off the student role's grants too.
        """
        employee = await self.get_employee(employee_id, organization_id)
        if employee.user_id:
            raise ConflictError("This employee already has portal access.")
        if not employee.email:
            raise ValidationError("This employee has no email on file — add one before inviting them.")

        existing_user = await self.auth_repo.get_user_by_email(employee.email)
        if existing_user:
            raise ConflictError(f"An account already exists for {employee.email}.")

        user = await self.auth_repo.create_user(
            email=employee.email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            full_name=employee.full_name,
            phone_number=employee.phone,
        )
        user.is_email_verified = True
        user.status = UserStatus.ACTIVE
        await self.db.flush()

        await self.profile_repo.create(user_id=user.id, organization_id=organization_id)
        employee = await self.repo.update(employee, user_id=user.id)

        reset_token = await self.auth_repo.create_password_reset_token(
            user.id, ttl_hours=_INVITE_TOKEN_TTL_HOURS
        )
        set_password_url = f"{settings.EMPLOYEE_PORTAL_URL}/reset-password?token={reset_token.token}"
        send_password_reset_email_task.delay(user.email, user.full_name, set_password_url)

        logger.info("employee_invited", employee_id=str(employee_id), user_id=str(user.id))
        return employee
