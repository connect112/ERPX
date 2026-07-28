import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.accounting.ledger.models import AccountType


class AccountCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=2, max_length=255)
    account_type: AccountType
    account_subtype: str | None = Field(default=None, max_length=100)
    parent_account_id: uuid.UUID | None = None
    description: str | None = None
    opening_balance: float = Field(default=0, ge=0)


class AccountUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    account_subtype: str | None = None
    parent_account_id: uuid.UUID | None = None
    description: str | None = None
    is_active: bool | None = None


class AccountPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    parent_account_id: uuid.UUID | None
    code: str
    name: str
    account_type: AccountType
    account_subtype: str | None
    description: str | None
    opening_balance: float
    is_system_account: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountBalanceResponse(BaseModel):
    account_id: uuid.UUID
    code: str
    name: str
    account_type: AccountType
    as_of_date: date | None
    opening_balance: float
    total_debit: float
    total_credit: float
    closing_balance: float


class MessageResponse(BaseModel):
    message: str
