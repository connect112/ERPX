"""
Dashboard module — service layer.

Purely aggregates data already owned by other modules (Organizations,
Branches, Users, Authorization). Holds no models or tables of its own —
as CRM, Students, Accounting etc. come online, their own counts/widgets
get added here.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from modules.authorization.repository import AuthorizationRepository
from modules.branches.repository import BranchRepository
from modules.dashboard.schemas import DashboardSummaryResponse
from modules.organizations.repository import OrganizationRepository
from modules.users.repository import UserProfileRepository


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.org_repo = OrganizationRepository(db)
        self.branch_repo = BranchRepository(db)
        self.user_repo = UserProfileRepository(db)
        self.authz_repo = AuthorizationRepository(db)

    async def get_summary(self, organization_id: uuid.UUID) -> DashboardSummaryResponse:
        org = await self.org_repo.get_by_id(organization_id)
        if not org:
            raise NotFoundError("Organization", organization_id)

        total_users = await self.user_repo.count_for_organization(organization_id)
        total_branches = await self.branch_repo.count_for_organization(organization_id)
        total_roles = await self.authz_repo.count_roles()

        return DashboardSummaryResponse(
            organization_name=org.name,
            subscription_plan=org.subscription_plan,
            total_users=total_users,
            total_branches=total_branches,
            total_roles=total_roles,
            organization_created_at=org.created_at,
        )
