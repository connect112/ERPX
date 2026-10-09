"""Scheduling, publishing controls, the queue, attempts and the calendar."""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.social_media.models import PostStatus, SocialPost
from modules.social_media.publisher import CAPTION_LIMIT, PublisherService, compose_caption, utcnow
from modules.social_media.schemas import (
    AttemptPublic,
    CalendarItem,
    CalendarOut,
    PostPublic,
    QueueItem,
    QueueOut,
    ReadinessOut,
    ReconcileOut,
    ResolveRequest,
    ScheduleRequest,
)
from modules.social_media.service import PostService, SettingsService
from modules.social_media.tasks import enqueue_publish
from modules.users.dependencies import get_current_user_organization_id
from packages.storage.client import get_storage_client

router = APIRouter()

VIEW = "social_media.view"
PUBLISH = "social_media.publish"
QUEUE_STATES = (PostStatus.SCHEDULED.value, PostStatus.PUBLISHING.value, PostStatus.FAILED.value, PostStatus.PUBLISH_UNKNOWN.value)
MAX_CALENDAR_DAYS = 62


def _thumbnail(post: SocialPost) -> str | None:
    files = (post.artwork or {}).get("files") or []
    if not files:
        return None
    try:
        return get_storage_client().presigned_download_url(files[0]["key"])
    except Exception:  # noqa: BLE001 - a missing picture must not break the calendar
        return None


def _item(post: SocialPost, zone: ZoneInfo) -> CalendarItem:
    local = post.scheduled_at.astimezone(zone)
    return CalendarItem(
        id=post.id,
        title=post.title,
        status=post.status,
        format=post.format,
        pillar=post.pillar,
        scheduled_at=post.scheduled_at,
        local_date=local.date().isoformat(),
        local_time=local.strftime("%H:%M"),
        thumbnail=_thumbnail(post),
        time_sensitive=post.time_sensitive,
        high_risk=post.high_risk,
    )


# ---------------- is this post ready? ----------------


@router.get("/posts/{post_id}/readiness", response_model=ReadinessOut)
async def readiness(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """What stops this post from being published now, and the exact caption that would be posted."""
    settings = await SettingsService(db).get(organization_id)
    post = await PostService(db).get(post_id, organization_id)
    publisher = PublisherService(db)
    account = await publisher.account(organization_id)
    problems = publisher.readiness(post, settings, account)
    caption = compose_caption(post)
    result = ReadinessOut(
        ready=not problems,
        problems=problems,
        caption=caption,
        caption_length=len(caption),
        caption_limit=CAPTION_LIMIT,
        publish_mode=settings.publish_mode,
        timezone=settings.timezone,
        account_connected=account is not None and account.status in ("connected", "expiring"),
        note="Stories are published without a caption." if post.format == "story" else "This is exactly what will be posted as the caption.",
    )
    await db.commit()
    return result


# ---------------- explicit actions (each needs the publish permission) ----------------


@router.post("/posts/{post_id}/schedule", response_model=PostPublic)
async def schedule_post(
    post_id: uuid.UUID,
    payload: ScheduleRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(PUBLISH)),
    db: AsyncSession = Depends(get_db),
):
    """Schedule an approved post (or move a scheduled one). A time without a zone is read in the account timezone."""
    settings = await SettingsService(db).get(organization_id)
    post = await PostService(db).get(post_id, organization_id)
    await PublisherService(db).schedule(post, settings, payload.scheduled_at)
    await db.refresh(post)
    result = PostService.public(post)
    await db.commit()
    return result


@router.post("/posts/{post_id}/unschedule", response_model=PostPublic)
async def unschedule_post(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(PUBLISH)),
    db: AsyncSession = Depends(get_db),
):
    post = await PostService(db).get(post_id, organization_id)
    await PublisherService(db).unschedule(post)
    await db.refresh(post)
    result = PostService.public(post)
    await db.commit()
    return result


@router.post("/posts/{post_id}/publish-now", response_model=PostPublic)
async def publish_now(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(PUBLISH)),
    db: AsyncSession = Depends(get_db),
):
    """Publish an approved post now (an explicit click). The worker picks it up within a minute; this also queues it at once."""
    settings = await SettingsService(db).get(organization_id)
    post = await PostService(db).get(post_id, organization_id)
    await PublisherService(db).publish_now(post, settings)
    await db.refresh(post)
    result = PostService.public(post)
    await db.commit()
    enqueue_publish(post.id, user.id)
    return result


@router.post("/posts/{post_id}/retry", response_model=PostPublic)
async def retry_post(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(PUBLISH)),
    db: AsyncSession = Depends(get_db),
):
    """Put a failed post (one that is certainly not on Instagram) back in the queue."""
    settings = await SettingsService(db).get(organization_id)
    post = await PostService(db).get(post_id, organization_id)
    await PublisherService(db).retry(post, settings)
    await db.refresh(post)
    result = PostService.public(post)
    await db.commit()
    enqueue_publish(post.id, user.id)
    return result


@router.post("/posts/{post_id}/reconcile", response_model=ReconcileOut)
async def reconcile_post(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(PUBLISH)),
    db: AsyncSession = Depends(get_db),
):
    """Ask Instagram what happened to a post whose outcome was unclear. It never publishes anything itself."""
    post = await PostService(db).get(post_id, organization_id)
    outcome = await PublisherService(db).reconcile(post)
    await db.refresh(post)
    result = ReconcileOut(outcome=outcome.state, note=outcome.note, post=PostService.public(post))
    await db.commit()
    return result


@router.post("/posts/{post_id}/resolve", response_model=PostPublic)
async def resolve_post(
    post_id: uuid.UUID,
    payload: ResolveRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(PUBLISH)),
    db: AsyncSession = Depends(get_db),
):
    """A person checked Instagram and records whether the post is there."""
    post = await PostService(db).get(post_id, organization_id)
    await PublisherService(db).resolve(post, payload.published, payload.media_id, payload.permalink)
    await db.refresh(post)
    result = PostService.public(post)
    await db.commit()
    return result


@router.get("/posts/{post_id}/attempts", response_model=list[AttemptPublic])
async def attempts(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """The publishing history of a post: every attempt, what Instagram said, and when."""
    post = await PostService(db).get(post_id, organization_id)
    return [AttemptPublic.model_validate(a) for a in await PublisherService(db).attempts(post.id)]


# ---------------- the queue and the calendar ----------------


@router.get("/queue", response_model=QueueOut)
async def queue(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """Everything waiting to go out, going out now, failed or with an unclear outcome."""
    settings = await SettingsService(db).get(organization_id)
    rows = (
        await db.execute(
            select(SocialPost)
            .where(SocialPost.organization_id == organization_id, SocialPost.status.in_(QUEUE_STATES))
            .order_by(SocialPost.scheduled_at.asc().nullslast(), SocialPost.created_at)
            .limit(100)
        )
    ).scalars().all()
    publisher = PublisherService(db)
    items = []
    for post in rows:
        last = await publisher._latest_attempt(post.id)
        items.append(QueueItem(post=PostService.public(post), last_attempt=AttemptPublic.model_validate(last) if last else None))
    await db.commit()
    return QueueOut(
        items=items,
        timezone=settings.timezone,
        worker_note="A background worker checks every minute for posts whose time has come. Failed and unclear posts are never retried without your action once Instagram might have received them.",
    )


@router.get("/calendar", response_model=CalendarOut)
async def calendar(
    start: date = Query(...),
    end: date = Query(...),
    include_cancelled: bool = Query(default=False),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """Posts with a planned or scheduled time between two dates (in the account timezone), and approved posts with no time yet."""
    if end < start or (end - start).days > MAX_CALENDAR_DAYS:
        raise ValidationError(f"Ask for at most {MAX_CALENDAR_DAYS} days, with the end date after the start.")
    settings = await SettingsService(db).get(organization_id)
    zone = ZoneInfo(settings.timezone)
    lower = datetime.combine(start, time.min, tzinfo=zone).astimezone(timezone.utc)
    upper = datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc)
    conditions = [SocialPost.organization_id == organization_id, SocialPost.scheduled_at >= lower, SocialPost.scheduled_at < upper]
    if not include_cancelled:
        conditions.append(SocialPost.status != PostStatus.CANCELLED.value)
    rows = (await db.execute(select(SocialPost).where(*conditions).order_by(SocialPost.scheduled_at))).scalars().all()
    waiting = (
        await db.execute(
            select(SocialPost)
            .where(SocialPost.organization_id == organization_id, SocialPost.status == PostStatus.APPROVED.value, SocialPost.scheduled_at.is_(None))
            .order_by(SocialPost.approved_at)
            .limit(50)
        )
    ).scalars().all()
    result = CalendarOut(
        start=start.isoformat(),
        end=end.isoformat(),
        timezone=settings.timezone,
        publish_mode=settings.publish_mode,
        items=[_item(p, zone) for p in rows],
        # approved posts with no time: shown at "now" only to fit the shape; the page lists them separately
        ready_to_schedule=[_item_unscheduled(p, zone) for p in waiting],
    )
    await db.commit()
    return result


def _item_unscheduled(post: SocialPost, zone: ZoneInfo) -> CalendarItem:
    stamp = post.approved_at or utcnow()
    local = stamp.astimezone(zone)
    return CalendarItem(
        id=post.id,
        title=post.title,
        status=post.status,
        format=post.format,
        pillar=post.pillar,
        scheduled_at=stamp,
        local_date=local.date().isoformat(),
        local_time=local.strftime("%H:%M"),
        thumbnail=_thumbnail(post),
        time_sensitive=post.time_sensitive,
        high_risk=post.high_risk,
    )
