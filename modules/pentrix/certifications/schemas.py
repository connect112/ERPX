import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class IssueCertificationRequest(BaseModel):
    student_id: uuid.UUID
    track_name: str = Field(..., min_length=2, max_length=255)
    minimum_points: int = Field(default=0, ge=0)
    force: bool = False


class CertificationPublic(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    track_name: str
    certificate_number: str
    points_at_issuance: int
    issued_at: datetime

    model_config = {"from_attributes": True}


class CertificationVerificationResponse(BaseModel):
    valid: bool
    certificate_number: str
    student_name: str | None = None
    track_name: str | None = None
    points_at_issuance: int | None = None
    issued_at: datetime | None = None
