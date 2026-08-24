import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class ProvisionStudentRequest(BaseModel):
    """Body of POST /api/v1/internal/provisioning/students.

    `payment_reference` is the idempotency key (Pentrix's `payment.id`) —
    a retried call with the same value never creates a second user.
    `program_code` identifies which ERPX course this maps to (resolved by
    slug against the seeded Pentrix organization); an unrecognized code
    fails clearly (422) rather than silently skipping enrollment.
    """

    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    program_code: str = Field(..., min_length=1, max_length=255)
    payment_reference: str = Field(..., min_length=1, max_length=255)
    amount_paise: int = Field(..., ge=0)
    paid_at: datetime


class ProvisionStudentResponse(BaseModel):
    user_id: uuid.UUID
    status: Literal["created", "already_exists"]
    login_url: str
