import uuid
from datetime import datetime

from pydantic import BaseModel


class IssueCertificateRequest(BaseModel):
    student_id: uuid.UUID
    course_id: uuid.UUID
    force: bool = False  # bypass the 100%-completion requirement


class CertificatePublic(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    certificate_number: str
    issued_at: datetime

    model_config = {"from_attributes": True}


class CertificateVerificationResponse(BaseModel):
    valid: bool
    certificate_number: str
    student_name: str | None = None
    course_title: str | None = None
    issued_at: datetime | None = None
