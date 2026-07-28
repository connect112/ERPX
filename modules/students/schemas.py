import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.students.models import StudentStatus
from modules.users.models import Gender


class StudentCreateRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    full_name: str = Field(..., min_length=2, max_length=255)
    email: str | None = None
    phone: str | None = None
    gender: Gender | None = None
    date_of_birth: date | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    course_name: str = Field(..., min_length=2, max_length=255)
    batch_name: str | None = None
    enrollment_date: date
    notes: str | None = None


class StudentFromAdmissionRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    enrollment_date: date | None = None  # defaults to today if omitted


class StudentUpdateRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    gender: Gender | None = None
    date_of_birth: date | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    batch_name: str | None = None
    notes: str | None = None


class StudentStatusChangeRequest(BaseModel):
    status: StudentStatus
    notes: str | None = None


class StudentPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    admission_id: uuid.UUID | None
    user_id: uuid.UUID | None
    student_code: str
    full_name: str
    email: str | None
    phone: str | None
    gender: Gender | None
    date_of_birth: date | None
    guardian_name: str | None
    guardian_phone: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    course_name: str
    batch_name: str | None
    enrollment_date: date
    status: StudentStatus
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
