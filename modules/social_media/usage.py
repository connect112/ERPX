"""
Cost of the paid AI calls. The figure is an ESTIMATE: tokens used times the prices in the settings
(SOCIAL_AI_INPUT_USD_PER_MTOK, SOCIAL_AI_OUTPUT_USD_PER_MTOK, SOCIAL_USD_TO_INR), not an invoice.
A monthly budget (0 = no limit) stops further AI calls once it is used up and warns at the chosen percentage.
"""

import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.exceptions import ValidationError
from modules.social_media.models import AIUsage, SocialSettings
from packages.ai.client import AICompletionResult


def estimate_cost_inr(input_tokens: int, output_tokens: int) -> Decimal:
    usd = (
        Decimal(input_tokens) * Decimal(str(app_settings.SOCIAL_AI_INPUT_USD_PER_MTOK))
        + Decimal(output_tokens) * Decimal(str(app_settings.SOCIAL_AI_OUTPUT_USD_PER_MTOK))
    ) / Decimal(1_000_000)
    return (usd * Decimal(str(app_settings.SOCIAL_USD_TO_INR))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def month_start(settings: SocialSettings, now: datetime | None = None) -> datetime:
    """The start of this month in the account timezone, as UTC."""
    zone = ZoneInfo(settings.timezone)
    local = (now or datetime.now(timezone.utc)).astimezone(zone)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


class UsageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def spent(self, organization_id: uuid.UUID, settings: SocialSettings) -> Decimal:
        total = (
            await self.db.execute(
                select(func.coalesce(func.sum(AIUsage.est_cost_inr), 0)).where(
                    AIUsage.organization_id == organization_id, AIUsage.created_at >= month_start(settings)
                )
            )
        ).scalar_one()
        return Decimal(total)

    async def check_budget(self, organization_id: uuid.UUID, settings: SocialSettings) -> None:
        budget = Decimal(str((settings.budgets or {}).get("monthly_budget_inr") or 0))
        if budget > 0 and await self.spent(organization_id, settings) >= budget:
            raise ValidationError(
                "This month's AI budget has been used up, so no more AI calls are made. "
                "Raise the budget under Settings or wait for next month."
            )

    async def record(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        post_id: uuid.UUID | None,
        kind: str,
        result: AICompletionResult,
    ) -> AIUsage:
        row = AIUsage(
            organization_id=organization_id,
            user_id=user_id,
            post_id=post_id,
            kind=kind,
            model=result.model or "unknown",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            est_cost_inr=estimate_cost_inr(result.input_tokens, result.output_tokens),
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def summary(self, organization_id: uuid.UUID, settings: SocialSettings) -> dict:
        since = month_start(settings)
        rows = (
            await self.db.execute(
                select(AIUsage.kind, func.count(), func.coalesce(func.sum(AIUsage.est_cost_inr), 0))
                .where(AIUsage.organization_id == organization_id, AIUsage.created_at >= since)
                .group_by(AIUsage.kind)
            )
        ).all()
        by_kind = {kind: {"calls": calls, "est_cost_inr": float(cost)} for kind, calls, cost in rows}
        spent = sum(v["est_cost_inr"] for v in by_kind.values())
        budget = float((settings.budgets or {}).get("monthly_budget_inr") or 0)
        alert = int((settings.budgets or {}).get("alert_at_percent") or 80)
        return {
            "month_start": since,
            "spent_inr": round(spent, 2),
            "budget_inr": budget,
            "alert_at_percent": alert,
            "over_budget": budget > 0 and spent >= budget,
            "over_alert": budget > 0 and spent >= budget * alert / 100,
            "calls": sum(v["calls"] for v in by_kind.values()),
            "by_kind": by_kind,
            "is_estimate": True,
            "note": "An estimate from tokens used and the configured prices, not an invoice. A budget of 0 means no limit.",
        }
