import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from modules.accounting.expenses.models import ExpenseStatus


class ExpenseCreateRequest(BaseModel):
    vendor_id: uuid.UUID
    expense_account_id: uuid.UUID
    payable_account_id: uuid.UUID
    expense_number: str = Field(..., min_length=1, max_length=50)
    expense_date: datetime
    category: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=2)
    branch_id: uuid.UUID | None = None
    subtotal_amount: float = Field(..., gt=0)
    gst_rate_id: uuid.UUID | None = None
    input_tax_credit_account_id: uuid.UUID | None = None
    is_interstate: bool = False
    attachment_url: str | None = Field(default=None, max_length=512)
    notes: str | None = None

    @model_validator(mode="after")
    def _itc_account_required_with_gst(self):
        if self.gst_rate_id is not None and self.input_tax_credit_account_id is None:
            raise ValueError("input_tax_credit_account_id is required when gst_rate_id is set.")
        return self


class ExpenseUpdateRequest(BaseModel):
    expense_account_id: uuid.UUID | None = None
    payable_account_id: uuid.UUID | None = None
    expense_date: datetime | None = None
    category: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None
    subtotal_amount: float | None = Field(default=None, gt=0)
    gst_rate_id: uuid.UUID | None = None
    input_tax_credit_account_id: uuid.UUID | None = None
    is_interstate: bool | None = None
    attachment_url: str | None = None
    notes: str | None = None


class ExpenseRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=2)


class ExpensePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    vendor_id: uuid.UUID
    expense_account_id: uuid.UUID
    payable_account_id: uuid.UUID
    input_tax_credit_account_id: uuid.UUID | None
    gst_rate_id: uuid.UUID | None
    journal_entry_id: uuid.UUID | None
    approved_by_user_id: uuid.UUID | None
    expense_number: str
    expense_date: datetime
    category: str
    description: str
    is_interstate: bool
    subtotal_amount: float
    tax_amount: float
    total_amount: float
    amount_paid: float
    status: ExpenseStatus
    attachment_url: str | None
    rejection_reason: str | None
    notes: str | None
    approved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
