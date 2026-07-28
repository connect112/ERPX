import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.accounting.bank.models import BankAccountType, BankTransactionSource


class BankAccountCreateRequest(BaseModel):
    gl_account_id: uuid.UUID
    account_name: str = Field(..., min_length=2, max_length=255)
    account_type: BankAccountType = BankAccountType.CURRENT
    branch_id: uuid.UUID | None = None
    bank_name: str | None = None
    account_number: str | None = Field(default=None, max_length=34)
    ifsc_code: str | None = Field(default=None, max_length=11)
    opening_balance: float = Field(default=0)


class BankAccountUpdateRequest(BaseModel):
    account_name: str | None = Field(default=None, min_length=2, max_length=255)
    bank_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    is_active: bool | None = None


class BankAccountPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    gl_account_id: uuid.UUID
    account_name: str
    account_type: BankAccountType
    bank_name: str | None
    account_number: str | None
    ifsc_code: str | None
    opening_balance: float
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BankTransactionCreateRequest(BaseModel):
    transaction_date: datetime
    description: str = Field(..., min_length=2, max_length=500)
    debit_amount: float = Field(default=0, ge=0)
    credit_amount: float = Field(default=0, ge=0)
    reference_number: str | None = None
    contra_account_id: uuid.UUID = Field(
        ..., description="The other side of this bank-only movement (e.g. Bank Charges expense account)."
    )


class BankTransactionPublic(BaseModel):
    id: uuid.UUID
    bank_account_id: uuid.UUID
    journal_entry_id: uuid.UUID | None
    transaction_date: datetime
    description: str
    debit_amount: float
    credit_amount: float
    reference_number: str | None
    source: BankTransactionSource
    source_id: uuid.UUID | None
    is_reconciled: bool
    reconciled_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BankAccountBalanceResponse(BaseModel):
    bank_account_id: uuid.UUID
    account_name: str
    as_of_date: date | None
    opening_balance: float
    total_debit: float
    total_credit: float
    closing_balance: float


class MessageResponse(BaseModel):
    message: str
