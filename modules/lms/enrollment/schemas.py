import uuid
from datetime import date, datetime

from pydantic import BaseModel

from modules.lms.enrollment.models import EnrollmentStatus


class EnrollmentCreateRequest(BaseModel):
    student_id: uuid.UUID
    course_id: uuid.UUID
    enrolled_on: date | None = None


class EnrollmentStatusChangeRequest(BaseModel):
    status: EnrollmentStatus


class EnrollmentPublic(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    enrolled_on: date
    status: EnrollmentStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class MyInternshipRef(BaseModel):
    id: uuid.UUID
    title: str


class MyEnrollmentPublic(EnrollmentPublic):
    """A student's own enrolment, with the internships (their own) that gave them this course; empty for an ordinary course."""

    internships: list[MyInternshipRef] = []


class MessageResponse(BaseModel):
    message: str
