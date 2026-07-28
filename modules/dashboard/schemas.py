from datetime import datetime

from pydantic import BaseModel

from modules.organizations.models import SubscriptionPlan


class DashboardSummaryResponse(BaseModel):
    organization_name: str
    subscription_plan: SubscriptionPlan
    total_users: int
    total_branches: int
    total_roles: int
    organization_created_at: datetime
