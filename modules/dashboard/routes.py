import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.dashboard.schemas import DashboardSummaryResponse
from modules.dashboard.service import DashboardService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("dashboard.view")),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    return await service.get_summary(organization_id)
