from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_superuser
from modules.monitoring.schemas import HealthCheckResult, PlatformStatsResponse, SystemHealthResponse
from modules.monitoring.service import SystemHealthService

router = APIRouter()

# Both endpoints below are unavoidably platform-wide: infrastructure
# connection-pool/health internals aren't per-organization at all, and
# get_platform_stats() counts organizations/users/students/audit-events
# across every tenant with zero filter — there's no meaningful "my
# organization's system health" to show a tenant admin. Platform-operator
# only, gated by true is_superuser rather than a grantable permission.


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    user: User = Depends(require_superuser()),
    db: AsyncSession = Depends(get_db),
):
    service = SystemHealthService(db)
    checks = await service.get_all_checks()
    overall_status = "healthy" if all(c["status"] == "healthy" for c in checks) else "degraded"
    return SystemHealthResponse(
        overall_status=overall_status,
        checks=[HealthCheckResult(**c) for c in checks],
    )


@router.get("/stats", response_model=PlatformStatsResponse)
async def get_platform_stats(
    user: User = Depends(require_superuser()),
    db: AsyncSession = Depends(get_db),
):
    service = SystemHealthService(db)
    stats = await service.get_platform_stats()
    return PlatformStatsResponse(**stats)
