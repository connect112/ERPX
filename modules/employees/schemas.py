import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.employees.models import EmploymentStatus, EmploymentType
from modules.users.models import Gender


class EmployeeCreateRequest(BaseModel):
    employee_code: str = Field(..., min_length=1, max_length=30)
    full_name: str = Field(..., min_length=2, max_length=255)
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
