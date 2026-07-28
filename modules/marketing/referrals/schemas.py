import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.marketing.referrals.models import ReferralStatus


class ReferralProgramCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=1, max_length=30)
    referrer_reward_amount: float = Field(..., ge=0)
    referee_discount_amount: float = Field(default=0, ge=0)
    max_referrals_per_referrer: int | None = Field(default=None, ge=1)
    valid_from: date
    valid_until: date | None = None


class ReferralProgramUpdateRequest(BaseModel):
    referrer_reward_amount: float | None = Field(default=None, ge=0)
    referee_discount_amount: float | None = Field(default=None, ge=0)
    max_referrals_per_referrer: int | None = Field(default=None, ge=1)
    valid_until: date | None = None
    is_active: bool | None = None


class ReferralProgramPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: str
    referrer_reward_amount: float
    referee_discount_amount: float
    max_referrals_per_referrer: int | None
    valid_from: date
    valid_until: date | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralCreateRequest(BaseModel):
    referral_program_id: uuid.UUID
    referrer_student_id: uuid.UUID | None = None
    referee_name: str = Field(..., min_length=2, max_length=255)
    referee_email: str | None = None
    referee_phone: str | None = None


class ReferralPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    referral_program_id: uuid.UUID
    referrer_student_id: uuid.UUID | None
    converted_lead_id: uuid.UUID | None
    referee_name: str
    referee_email: str | None
    referee_phone: str | None
    status: ReferralStatus
    reward_amount: float | None
    rewarded_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralConvertRequest(BaseModel):
    converted_lead_id: uuid.UUID


class MessageResponse(BaseModel):
    message: str
