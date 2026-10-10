"""Health of the background jobs, retention of personal data, and erasure of one person's data.

Reading health needs `social_media.view`. Applying retention and erasing a person need `social_media.manage` (erasing also needs
`social_media.inbox`, because it removes inbox content). Both removals show what they would remove first and only act when asked
with `confirm: true`."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.social_media import health, retention
from modules.social_media.models import JobRun
from modules.social_media.service import SettingsService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
logger = get_logger(__name__)

VIEW = "social_media.view"
MANAGE = "social_media.manage"
INBOX = "social_media.inbox"


class RetentionRun(BaseModel):
    confirm: bool = False


class ErasePerson(BaseModel):
    handle: str = Field(min_length=1, max_length=101)
    confirm: bool = False


@router.get("/health")
async def job_health(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """Whether each scheduled job ran when it should have. A job that has never run is "not run yet", not a fault."""
    return {
        "jobs": await health.report(db, organization_id),
        "note": "Each job leaves a heartbeat when it finishes. A job that fails or goes quiet is shown here and emailed once a day to the addresses set in Settings.",
    }


@router.get("/privacy/retention")
async def retention_status(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """The retention period, what is already past it, and what the last daily run removed."""
    settings = await SettingsService(db).get(organization_id)
    would = await retention.preview(db, organization_id, settings.retention_days)
    last = (await db.execute(select(JobRun).where(JobRun.job == "apply_retention"))).scalar_one_or_none()
    return {
        "retention_days": settings.retention_days,
        "past_the_period": would,
        "last_run_at": last.last_finished_at if last else None,
        "last_run_ok": last.last_ok if last else None,
        "last_run_removed": (last.detail if last else None) or None,
        "keeps": [
            "The record of who sent each reply, when, and how it ended (the text of the reply is removed).",
            "Weekly and monthly reports and daily account figures: they hold counts only, no personal data.",
            "CRM leads: the CRM keeps its own leads under its own rules.",
        ],
    }


@router.post("/privacy/retention/run")
async def run_retention(
    payload: RetentionRun,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Remove what is past the retention period now (the same thing the daily run does). Needs `confirm: true`."""
    settings = await SettingsService(db).get(organization_id)
    if not payload.confirm:
        return {"removed": None, "would_remove": await retention.preview(db, organization_id, settings.retention_days)}
    removed = await retention.apply(db, organization_id, settings.retention_days)
    logger.info("social_retention_run_by_person", user_id=str(user.id), **removed)
    await db.commit()
    return {"removed": removed, "would_remove": None}


@router.post("/privacy/erase")
async def erase_person(
    payload: ErasePerson,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE, INBOX)),
    db: AsyncSession = Depends(get_db),
):
    """Remove one person's comments, conversations and messages (and the text of replies to them) at their request.
    Without `confirm: true` it only counts. CRM leads made from their enquiries stay in the CRM and are handled there."""
    result = await retention.erase_person(db, organization_id, payload.handle, payload.confirm)
    if result["erased"]:
        logger.info("social_person_erased", user_id=str(user.id), comments=result["comments"], conversations=result["conversations"], messages=result["messages"])
        await db.commit()
    return result
