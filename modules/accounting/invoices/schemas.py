import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.accounting.invoices.models import InvoiceStatus


class InvoiceLineRequest(BaseModel):
    revenue_account_id: uuid.UUID
    description: str = Field(..., min_length=1, max_length=500)
    quantity: float = Field(default=1, gt=0)
    unit_price: float = Field(..., ge=0)
    gst_rate_id: uuid.UUID | None = None


class InvoiceCreateRequest(BaseModel):
    customer_id: uuid.UUID
    invoice_number: str = Field(..., min_length=1, max_length=50)
    invoice_date: datetime
    due_date: datetime
    receivable_account_id: uuid.UUID
    tax_payable_account_id: uuid.UUID | None = None
    discount_account_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    is_interstate: bool = False
    discount_amount: float = Field(default=0, ge=0)
    notes: str | None = None
    lines: list[InvoiceLineRequest] = Field(..., min_length=1)


class InvoiceUpdateRequest(BaseModel):
    invoice_date: datetime | None = None
    due_date: datetime | None = None
    receivable_account_id: uuid.UUID | None = None
    tax_payable_account_id: uuid.UUID | None = None
    discount_account_id: uuid.UUID | None = None
    is_interstate: bool | None = None
    discount_amount: float | None = Field(default=None, ge=0)
    notes: str | None = None
    lines: list[InvoiceLineRequest] | None = None


class InvoiceLinePublic(BaseModel):
    id: uuid.UUID
    revenue_account_id: uuid.UUID
    gst_rate_id: uuid.UUID | None
    description: str
    quantity: float
    unit_price: float
    line_subtotal: float
    tax_amount: float
    line_total: float

    model_config = {"from_attributes": True}


class InvoicePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    customer_id: uuid.UUID
    receivable_account_id: uuid.UUID
    tax_payable_account_id: uuid.UUID | None
    discount_account_id: uuid.UUID | None
    journal_entry_id: uuid.UUID | None
    invoice_number: str
    invoice_date: datetime
    due_date: datetime
    is_interstate: bool
    subtotal_amount: float
    tax_amount: float
    discount_amount: float
    total_amount: float
    amount_paid: float
    status: InvoiceStatus
    notes: str | None
    created_at: datetime
    lines: list[InvoiceLinePublic] = []

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
