import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.corporate.reports.schemas import (
    ClientSummaryResponse,
    TicketSLASummaryResponse,
    VAPTPortfolioSummaryResponse,
)
from modules.corporate.reports.service import CorporateReportService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/clients/{client_id}/summary", response_model=ClientSummaryResponse)
async def get_client_summary(
    client_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.reports.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CorporateReportService(db)
    summary = await service.client_summary(client_id, organization_id)
    return ClientSummaryResponse(**summary)


@router.get("/vapt/portfolio-summary", response_model=VAPTPortfolioSummaryResponse)
async def get_vapt_portfolio_summary(
    as_of_date: date = Query(default_factory=date.today),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.reports.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CorporateReportService(db)
    summary = await service.vapt_portfolio_summary(organization_id, as_of_date)
    return VAPTPortfolioSummaryResponse(**summary)


@router.get("/tickets/sla-summary", response_model=TicketSLASummaryResponse)
async def get_ticket_sla_summary(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.reports.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CorporateReportService(db)
    summary = await service.ticket_sla_summary(organization_id)
    return TicketSLASummaryResponse(**summary)
