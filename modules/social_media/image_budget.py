"""
A hard, server-side limit on generated images (the testing budget): at most SOCIAL_IMAGE_MAX_ASSETS images and SOCIAL_IMAGE_BUDGET_USD
dollars in total, however many requests, jobs, workers or retries there are.

How it is enforced, without a new table: every generation ATTEMPT first writes a reservation row into `social_ai_usage` (kind "image",
priced at a conservative estimate) and commits it before the provider is called, under a database advisory lock per organisation. The limit is checked against the rows already there while holding that lock, so two requests at the same moment
cannot both take the last slot. A failed or retried attempt keeps its row: the provider may have charged for it, so it counts.
The figures are estimates (the provider's invoice is the truth); the estimate is deliberately on the high side.

A second advisory lock per post stops the same post from being generated twice at once (a double click, a retry while the first
call is still running).
"""

import hashlib
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.exceptions import ConflictError, ValidationError
from app.db.session import engine
from modules.social_media.models import AIUsage

KIND = "image"
# Rough prices per image by quality (USD), on the high side. With no quality configured the worst case is assumed.
_EST_USD = {"low": 0.02, "medium": 0.07, "high": 0.25}
WORST_CASE_USD = 0.25


def est_usd() -> float:
    """The estimated cost of one generated image, never lower than what the settings imply."""
    if app_settings.SOCIAL_IMAGE_COST_USD and app_settings.SOCIAL_IMAGE_COST_USD > 0:
        return float(app_settings.SOCIAL_IMAGE_COST_USD)
    return _EST_USD.get((app_settings.SOCIAL_IMAGE_QUALITY or "").strip().lower(), WORST_CASE_USD)


def _key(prefix: str, ident: uuid.UUID) -> int:
    """A signed 63-bit number for pg advisory locks."""
    digest = hashlib.sha1(f"{prefix}:{ident}".encode()).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFFFFFFFFFF


async def status(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    used, cost_inr = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(AIUsage.est_cost_inr), 0)).where(
                AIUsage.organization_id == organization_id, AIUsage.kind == KIND
            )
        )
    ).one()
    rate = Decimal(str(app_settings.SOCIAL_USD_TO_INR or 1))
    spent = float((Decimal(cost_inr) / rate).quantize(Decimal("0.0001")))
    max_assets = int(app_settings.SOCIAL_IMAGE_MAX_ASSETS)
    budget = float(app_settings.SOCIAL_IMAGE_BUDGET_USD)
    return {
        "assets_used": int(used),
        "assets_max": max_assets,
        "assets_left": max(0, max_assets - int(used)),
        "spent_usd_est": round(spent, 2),
        "budget_usd": budget,
        "est_usd_per_image": est_usd(),
        "is_estimate": True,
        "note": "A hard testing limit. Failed attempts count too, because the provider may have charged for them. The cost is an estimate; the provider's invoice is the truth.",
    }


async def reserve(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID | None, post_id: uuid.UUID | None, model: str) -> uuid.UUID:
    """Take one slot, or refuse. The reservation is committed at once, before the provider is called, so a crash, a timeout or a retry
    can never make an attempt uncounted. (It commits the caller's session, so call it before changing anything else.)"""
    await db.execute(text("select pg_advisory_xact_lock(:k)"), {"k": _key("social-image-budget", organization_id)})
    current = await status(db, organization_id)
    if current["assets_used"] >= current["assets_max"]:
        raise ValidationError(
            f"The image testing limit is reached: {current['assets_used']} of {current['assets_max']} images have been made. No more are generated."
        )
    estimate = est_usd()
    if current["spent_usd_est"] + estimate > current["budget_usd"] + 1e-9:
        raise ValidationError(
            f"The image testing budget would be exceeded: about ${current['spent_usd_est']:.2f} of ${current['budget_usd']:.2f} is used and one more image is estimated at ${estimate:.2f}."
        )
    rate = Decimal(str(app_settings.SOCIAL_USD_TO_INR or 1))
    row = AIUsage(
        organization_id=organization_id,
        user_id=user_id,
        post_id=post_id,
        kind=KIND,
        model=(model or "unknown")[:100],
        input_tokens=0,
        output_tokens=0,
        est_cost_inr=(Decimal(str(estimate)) * rate).quantize(Decimal("0.0001")),
    )
    db.add(row)
    await db.flush()
    reservation = row.id
    await db.commit()  # releases the advisory lock too: the slot is now taken for everyone else
    return reservation


@asynccontextmanager
async def one_at_a_time(post_id: uuid.UUID):
    """Held while an image is being made for a post; a second request for the same post is refused instead of paying twice.
    It uses its own connection, so the lock lives exactly as long as this block and can never leak into the connection pool."""
    async with engine.connect() as conn:
        key = _key("social-image-post", post_id)
        got = (await conn.execute(text("select pg_try_advisory_lock(:k)"), {"k": key})).scalar_one()
        if not got:
            raise ConflictError("An illustration for this post is already being made. Wait for it to finish.")
        try:
            yield
        finally:
            await conn.execute(text("select pg_advisory_unlock(:k)"), {"k": key})
