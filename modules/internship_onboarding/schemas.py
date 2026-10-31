import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ConfigSaveRequest(BaseModel):
    settings: dict


class ApplyTemplateRequest(BaseModel):
    template_id: uuid.UUID


class TemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    settings: dict = Field(default_factory=dict)
    from_internship_id: uuid.UUID | None = None


class TemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    settings: dict | None = None


class TemplateDuplicateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class TemplateArchiveRequest(BaseModel):
    archived: bool = True


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    version: int
    archived: bool
    settings: dict
    updated_at: datetime


class StudentIdsRequest(BaseModel):
    student_ids: list[uuid.UUID] = Field(min_length=1, max_length=2000)


class ReopenRequest(BaseModel):
    student_ids: list[uuid.UUID] = Field(min_length=1, max_length=2000)
    until: datetime
    reason: str = Field(min_length=1, max_length=1000)
    late_fee: Literal["none", "config", "custom", "waive"] = "none"
    late_fee_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class ReviewRequest(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


class DecisionRequest(BaseModel):
    approve: bool


class LinkOut(BaseModel):
    reference: str
    link: str
    note: str = "Any earlier link for this student no longer works."


class DraftRequest(BaseModel):
    step: str | None = Field(default=None, max_length=30)
    info: dict | None = None
    answers: dict | None = None


class AcceptRequest(BaseModel):
    confirmed: bool
    terms_version: str = Field(max_length=20)


class DeclineRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ManualPaymentRequest(BaseModel):
    method: Literal["bank_transfer", "upi"]
    reference: str = Field(min_length=4, max_length=120)
    paid_on: date
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    remarks: str | None = Field(default=None, max_length=1000)


class VerifyPaymentRequest(BaseModel):
    approve: bool
    amount_received: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    note: str | None = Field(default=None, max_length=1000)


class RecordPaymentRequest(BaseModel):
    method: Literal["bank_transfer", "upi", "cash", "other"]
    reference: str = Field(min_length=1, max_length=120)
    paid_on: date
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    note: str = Field(min_length=1, max_length=1000)


class RefundRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reason: str = Field(min_length=1, max_length=1000)


class RefundDecisionRequest(BaseModel):
    approve: bool
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class CancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
