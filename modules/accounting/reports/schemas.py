import uuid
from datetime import date

from pydantic import BaseModel

from modules.accounting.ledger.models import AccountType


class TrialBalanceLine(BaseModel):
    account_id: uuid.UUID
    code: str
    name: str
    account_type: AccountType
    debit_balance: float
    credit_balance: float


class TrialBalanceResponse(BaseModel):
    as_of_date: date
    lines: list[TrialBalanceLine]
    total_debit: float
    total_credit: float
    is_balanced: bool


class ProfitAndLossResponse(BaseModel):
    period_from: date
    period_to: date
    income_lines: list[TrialBalanceLine]
    expense_lines: list[TrialBalanceLine]
    total_income: float
    total_expense: float
    net_profit: float


class BalanceSheetResponse(BaseModel):
    as_of_date: date
    asset_lines: list[TrialBalanceLine]
    liability_lines: list[TrialBalanceLine]
    equity_lines: list[TrialBalanceLine]
    total_assets: float
    total_liabilities: float
    total_equity: float
    retained_earnings: float
    total_liabilities_and_equity: float
    is_balanced: bool


class AgingBucket(BaseModel):
    party_id: uuid.UUID
    party_name: str
    document_number: str
    document_date: date
    due_date: date
    outstanding_amount: float
    days_overdue: int
    bucket: str


class AgingReportResponse(BaseModel):
    as_of_date: date
    items: list[AgingBucket]
    total_outstanding: float
    bucket_totals: dict[str, float]
