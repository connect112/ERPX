import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from modules.employees.models import EmploymentStatus, EmploymentType
from modules.users.models import Gender


class EmployeeCreateRequest(BaseModel):
    """
    Required on every field except reporting_manager_id (the top of an org
    chart reports to no one — forcing this would make it impossible to
    ever create that employee) and notes (inherently free-form; there is
    sometimes genuinely nothing to note). branch_id and address_line2 stay
    optional too — neither is exposed in the admin "New employee" form at
    all, and forcing them here without a UI path to fill them in would
    just be an unreachable validation error.

    email in particular being required (it used to be optional) matters
    beyond data completeness: EmployeeService.invite_employee — the only
    way this record ever gets portal access — needs one to create the
    login, and previously had no way to fail earlier than that point.

    No employee_code field: it's system-generated (EMP-00001, EMP-00002, ...)
    by EmployeeRepository.create, the same sequential-with-retry pattern
    StudentRepository._next_student_code uses for student_code — an admin
    never types or sees a scheme to collide with.
    """

    full_name: str = Field(..., min_length=2, max_length=255)
    branch_id: uuid.UUID | None = None
    department_id: uuid.UUID
    designation_id: uuid.UUID
    reporting_manager_id: uuid.UUID | None = None
    email: EmailStr
    phone: str = Field(..., min_length=1, max_length=32)
    gender: Gender
    date_of_birth: date
    address_line1: str = Field(..., min_length=1, max_length=255)
    address_line2: str | None = None
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=1, max_length=100)
    postal_code: str = Field(..., min_length=1, max_length=20)
    emergency_contact_name: str = Field(..., min_length=1, max_length=255)
    emergency_contact_phone: str = Field(..., min_length=1, max_length=32)
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    date_of_joining: date
    notes: str | None = None


class EmployeeUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    branch_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    reporting_manager_id: uuid.UUID | None = None
    email: str | None = None
    phone: str | None = None
    gender: Gender | None = None
    date_of_birth: date | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    employment_type: EmploymentType | None = None
    notes: str | None = None


class EmployeeStatusChangeRequest(BaseModel):
    employment_status: EmploymentStatus
    date_of_exit: date | None = None


class EmployeePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    user_id: uuid.UUID | None
    department_id: uuid.UUID | None
    designation_id: uuid.UUID | None
    reporting_manager_id: uuid.UUID | None
    employee_code: str
    full_name: str
    email: str | None
    phone: str | None
    gender: Gender | None
    date_of_birth: date | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    employment_type: EmploymentType
    employment_status: EmploymentStatus
    date_of_joining: date
    date_of_exit: date | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
