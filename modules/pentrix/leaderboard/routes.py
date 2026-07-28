import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.pentrix.leaderboard.service import LeaderboardEntry, LeaderboardService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.leaderboard.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaderboardService(db)
    return await service.get_leaderboard(organization_id, limit)
