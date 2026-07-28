import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.reports.schemas import (
    AgingReportResponse,
    BalanceSheetResponse,
    ProfitAndLossResponse,
    TrialBalanceResponse,
)
from modules.accounting.reports.service import ReportService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def get_trial_balance(
    as_of_date: date = Query(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.reports.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ReportService(db)
    report = await service.trial_balance(organization_id, as_of_date)
    return TrialBalanceResponse(**report)


@router.get("/profit-and-loss", response_model=ProfitAndLossResponse)
async def get_profit_and_loss(
    period_from: date = Query(...),
    period_to: date = Query(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.reports.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ReportService(db)
    report = await service.profit_and_loss(organization_id, period_from, period_to)
    return ProfitAndLossResponse(**report)


@router.get("/balance-sheet", response_model=BalanceSheetResponse)
async def get_balance_sheet(
    as_of_date: date = Query(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.reports.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ReportService(db)
    report = await service.balance_sheet(organization_id, as_of_date)
    return BalanceSheetResponse(**report)


@router.get("/aging/receivables", response_model=AgingReportResponse)
async def get_ar_aging(
    as_of_date: date = Query(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.reports.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ReportService(db)
    report = await service.accounts_receivable_aging(organization_id, as_of_date)
    return AgingReportResponse(**report)


@router.get("/aging/payables", response_model=AgingReportResponse)
async def get_ap_aging(
    as_of_date: date = Query(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.reports.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ReportService(db)
    report = await service.accounts_payable_aging(organization_id, as_of_date)
    return AgingReportResponse(**report)
