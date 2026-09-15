import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from modules.authentication.schemas import _validate_password_strength
from modules.employees.models import EmploymentStatus, EmploymentType
from modules.users.models import Gender


class EmployeeCreateRequest(BaseModel):
    """
    Required: the handful of fields HR actually knows on day one — name,
    org placement, a login-capable email, and a start date. Everything
    personal (phone, gender, DOB, address, emergency contact) is
    deliberately optional here and NOT collected from the admin at all —
    see EmployeeCompleteRegistrationRequest below. An admin invites an
    employee with just this much, the employee clicks the emailed link,
    sets their own password, and fills in the rest of their own profile
    themselves. That's also why email is required (unlike the personal
    fields): EmployeeService.invite_employee needs one to create the
    login, and previously had no way to fail earlier than that point.

    reporting_manager_id stays optional for its own reason (the top of an
    org chart reports to no one), and branch_id/notes are inherently
    optional/free-form.

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
    phone: str | None = Field(default=None, max_length=32)
    gender: Gender | None = None
    date_of_birth: date | None = None
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=32)
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


class EmployeeCompleteRegistrationRequest(BaseModel):
    """
    The public, token-authenticated counterpart to EmployeeCreateRequest's
    deliberately-thin admin form: everything personal that the admin
    *didn't* collect gets filled in here, by the employee themselves, in
    the same step as setting their own password. `token` is the same
    PasswordResetToken EmployeeService.invite_employee already generates —
    no new token type — so this reuses AuthService.reset_password's own
    validation (invalid/expired/already-used all rejected there) rather
    than duplicating it.
    """

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
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

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


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
