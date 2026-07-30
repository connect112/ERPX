import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_response
from app.core.config import settings
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
@cache_response(ttl=settings.CACHE_TTL_ANALYTICS, prefix="corporate.client_summary")
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
@cache_response(ttl=settings.CACHE_TTL_ANALYTICS, prefix="corporate.vapt_portfolio")
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
@cache_response(ttl=settings.CACHE_TTL_ANALYTICS, prefix="corporate.ticket_sla")
async def get_ticket_sla_summary(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.reports.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CorporateReportService(db)
    summary = await service.ticket_sla_summary(organization_id)
    return TicketSLASummaryResponse(**summary)
