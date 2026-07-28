import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.payroll.models import PayrollRunStatus, SalaryComponentType


class SalaryComponentCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=1, max_length=30)
    gl_account_id: uuid.UUID
    component_type: SalaryComponentType
    is_taxable: bool = True


class SalaryComponentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    gl_account_id: uuid.UUID | None = None
    is_taxable: bool | None = None
    is_active: bool | None = None


class SalaryComponentPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    gl_account_id: uuid.UUID
    name: str
    code: str
    component_type: SalaryComponentType
    is_taxable: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SalaryStructureLineRequest(BaseModel):
    salary_component_id: uuid.UUID
    amount: float = Field(..., ge=0)


class SalaryStructureCreateRequest(BaseModel):
    employee_id: uuid.UUID
    effective_from: date
    notes: str | None = None
    lines: list[SalaryStructureLineRequest] = Field(..., min_length=1)


class SalaryStructureLinePublic(BaseModel):
    id: uuid.UUID
    salary_component_id: uuid.UUID
    amount: float

    model_config = {"from_attributes": True}


class SalaryStructurePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    effective_from: date
    effective_to: date | None
    gross_monthly_amount: float
    total_deductions: float
    net_monthly_amount: float
    is_active: bool
    notes: str | None
    created_at: datetime
    lines: list[SalaryStructureLinePublic] = []

    model_config = {"from_attributes": True}


class PayrollRunGenerateRequest(BaseModel):
    period_year: int = Field(..., ge=2000, le=2100)
    period_month: int = Field(..., ge=1, le=12)
    run_date: date
    branch_id: uuid.UUID | None = None


class PayrollRunFinalizeRequest(BaseModel):
    net_payable_account_id: uuid.UUID


class PayrollRunMarkPaidRequest(BaseModel):
    bank_account_id: uuid.UUID
    payment_date: datetime


class PayslipLinePublic(BaseModel):
    id: uuid.UUID
    salary_component_id: uuid.UUID
    component_type: SalaryComponentType
    amount: float

    model_config = {"from_attributes": True}


class PayslipPublic(BaseModel):
    id: uuid.UUID
    payroll_run_id: uuid.UUID
    employee_id: uuid.UUID
    salary_structure_id: uuid.UUID
    days_in_month: int
    paid_days: float
    lop_days: float
    gross_amount: float
    total_deductions: float
    net_amount: float
    created_at: datetime
    lines: list[PayslipLinePublic] = []

    model_config = {"from_attributes": True}


class PayrollRunPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    net_payable_account_id: uuid.UUID | None
    bank_account_id: uuid.UUID | None
    journal_entry_id: uuid.UUID | None
    payment_journal_entry_id: uuid.UUID | None
    period_year: int
    period_month: int
    run_date: date
    status: PayrollRunStatus
    total_gross_amount: float
    total_deductions_amount: float
    total_net_amount: float
    finalized_at: datetime | None
    paid_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PayrollRunGenerationResult(BaseModel):
    run: PayrollRunPublic
    employees_processed: int
    employees_skipped_no_structure: list[uuid.UUID]


class MessageResponse(BaseModel):
    message: str
