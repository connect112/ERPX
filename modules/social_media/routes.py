import uuid
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, status
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.authorization.repository import AuthorizationRepository
from app.core.config import settings as app_settings
from modules.social_media import defaults, oauth
from modules.social_media.connection import computed_status, days_left
from modules.social_media.models import AccountDay, IgComment, IgConversation, MediaMetric, PostStatus, Report, SocialPost, SocialReply, WebhookEvent
from modules.social_media.schemas import (
    AccountPublic,
    BriefingItem,
    CapabilityInfo,
    IntegrationOverview,
    Overview,
    PostCreate,
    PostListResponse,
    PostPublic,
    PostTransition,
    PostUpdate,
    SettingsPublic,
    SettingsUpdate,
)
from modules.social_media.service import OverviewService, PostService, SettingsService
from modules.social_media.history import HistoryService
from modules.social_media.art_routes import router as art_router
from modules.social_media.analytics_routes import router as analytics_router
from modules.social_media.lead_routes import router as lead_router
from modules.social_media.ops_routes import router as ops_router
from modules.social_media.connect_routes import router as connect_router
from modules.social_media import health
from modules.social_media.analytics import AnalyticsService
from modules.social_media.attribution import AttributionService
from modules.social_media.inbox import InboxService
from modules.social_media.inbox_routes import router as inbox_router
from modules.social_media.publish_routes import router as publish_router
from modules.social_media.studio_routes import router as studio_router
from modules.social_media.usage import UsageService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
router.include_router(studio_router)
router.include_router(art_router)
router.include_router(publish_router)
router.include_router(connect_router)
router.include_router(inbox_router)
router.include_router(analytics_router)
router.include_router(lead_router)
router.include_router(ops_router)

VIEW = "social_media.view"
MANAGE = "social_media.manage"
APPROVE = "social_media.approve"

LIVE_KEYS = {
    "publish_image": "publish", "publish_carousel": "publish", "publish_story": "publish", "publish_reel": "publish",
    "comments_read": "comments", "comments_reply": "comments", "dm_read": "messages", "dm_reply": "messages",
    "insights": "insights", "webhooks": "webhooks",
}


def live_check(key: str, caps: dict, status_now: str) -> str:
    """What Instagram answered when the account was probed: passed, needs_app_review, failed, or not_run."""
    if key == "connect":
        return "passed" if status_now in ("connected", "expiring") else "not_run"
    state = caps.get(LIVE_KEYS.get(key, ""))
    if state in ("available", "subscribed"):
        return "passed"
    if state == "needs_app_review":
        return "needs_app_review"
    if state in ("unavailable", "error", "not_subscribed"):
        return "failed"
    return "not_run"


def verified(key: str, status_now: str, published: dict, webhook_events: int, proof: dict | None = None) -> bool:
    """True only when the real thing has happened with the real account (not merely that a permission check passed)."""
    if key == "connect":
        return status_now in ("connected", "expiring")
    if key in ("publish_image", "publish_carousel", "publish_story"):
        return published.get({"publish_image": "image", "publish_carousel": "carousel", "publish_story": "story"}[key], 0) > 0
    if key == "webhooks":
        return webhook_events > 0
    proof = proof or {}
    needed = {"comments_read": "comments", "dm_read": "conversations", "comments_reply": "comment_replies", "dm_reply": "dm_replies", "insights": "insight_values"}
    return key in needed and proof.get(needed[key], 0) > 0


SETUP_STEPS = [
    "Make sure the Instagram account is a Professional account (Business or Creator).",
    "At developers.facebook.com create an app (type Business), add the Instagram product and open \"API setup with Instagram login\".",
    "Under \"Set up Instagram business login\", add the redirect address shown below, exactly as it is.",
    "Under Roles, add the Instagram account as an Instagram tester, then accept the invitation in the Instagram app "
    "(Settings > Apps and websites > Tester invites).",
    "Under Webhooks, set the callback address and verify token shown below and subscribe to comments and messages. "
    "Meta only sends notifications once the app is Live.",
    "Put the app's ID and secret and your verify token in the server's environment (INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET, "
    "INSTAGRAM_WEBHOOK_VERIFY_TOKEN) and restart. Never paste them into chat or the repository.",
    "Press Connect Instagram below. For an account you own or manage and have added to the app, Meta's standard access is enough; "
    "other accounts, or live use of some features, need Meta's app review (advanced access).",
]


async def _can(db: AsyncSession, user: User, code: str) -> bool:
    if user.is_superuser:
        return True
    return code in await AuthorizationRepository(db).get_permission_codes_for_user(user.id)


# ---------------- overview ----------------


@router.get("/overview", response_model=Overview)
async def overview(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """The daily briefing: what needs attention, post counts by status, and the CRM leads that came from social media."""
    settings = await SettingsService(db).get(organization_id)
    service = OverviewService(db)
    counts = await service.post_counts(organization_id)
    account = await service.account(organization_id)
    connected = computed_status(account, datetime.now(timezone.utc)) in ("connected", "expiring")
    leads = await service.leads(organization_id)
    waiting, _ = await PostService(db).list(organization_id, status=PostStatus.REVIEW.value, limit=5)
    briefing = await service.briefing(counts, connected, settings, leads)
    history = HistoryService(db)
    considered = len(await history.recent(organization_id, limit=20))
    for suggestion in history.suggestions(await history.balance(organization_id, settings), considered):
        briefing.append(BriefingItem(level="info", message=f"Next batch: {suggestion}", link="studio"))
    usage = await UsageService(db).summary(organization_id, settings)
    if usage["over_budget"]:
        briefing.insert(0, BriefingItem(level="warning", message="The monthly AI budget is used up, so AI drafting is paused.", link="settings"))
    elif usage["over_alert"]:
        briefing.insert(0, BriefingItem(level="warning", message=f"AI spending has passed {usage['alert_at_percent']}% of the monthly budget (an estimate).", link="settings"))
    status_now = computed_status(account, datetime.now(timezone.utc))
    if status_now in ("expired", "revoked"):
        briefing.insert(0, BriefingItem(level="warning", message="The Instagram connection needs to be reconnected. Publishing and reading comments and messages are paused until then.", link="settings"))
    elif status_now == "expiring":
        briefing.append(BriefingItem(level="info", message="Instagram access expires soon. It is renewed automatically; reconnect if that fails.", link="settings"))
    if connected:
        inbox_counts = await InboxService(db).counts(organization_id)
        if inbox_counts["comments_unanswered"]:
            extra = f" ({inbox_counts['comments_enquiries']} look like course enquiries)" if inbox_counts["comments_enquiries"] else ""
            briefing.append(BriefingItem(level="action", message=f"{inbox_counts['comments_unanswered']} comment(s) are unanswered{extra}.", link="comments"))
        if inbox_counts["messages_need_reply"]:
            extra = f", {inbox_counts['messages_high_priority']} high priority" if inbox_counts["messages_high_priority"] else ""
            briefing.append(BriefingItem(level="action", message=f"{inbox_counts['messages_need_reply']} conversation(s) need a reply{extra}.", link="messages"))
    for job in (j for j in await health.report(db, organization_id) if j["state"] in ("failed", "late")):
        what = "failed on its last run" if job["state"] == "failed" else "hasn't run when it should"
        briefing.insert(0, BriefingItem(level="warning", message=f"Background job \"{job['label']}\" {what}. Look at the server's job log if this stays.", link=None))
    if connected:
        recent = [r for r in await AnalyticsService(db).posts(organization_id, limit=40) if r["kind"] != "story" and r["metrics"].get("reach") is not None]
        if len(recent) >= 4:
            reaches = sorted(r["metrics"]["reach"] for r in recent)
            typical = (reaches[len(reaches) // 2] + reaches[(len(reaches) - 1) // 2]) / 2
            best = max(recent, key=lambda r: r["metrics"]["reach"])
            if typical and best["metrics"]["reach"] >= 1.25 * typical:
                briefing.append(BriefingItem(level="info", message=f"Strongest recent post: \"{(best['title'] or best['caption'] or 'a post')[:60]}\" reached {best['metrics']['reach']:,.0f} accounts, against a typical {typical:,.0f}.", link="analytics"))
    attention = await AttributionService(db).attention(organization_id)
    if attention["needs_first_contact"]:
        briefing.append(BriefingItem(level="action", message=f"{attention['needs_first_contact']} lead(s) from social media haven't been contacted yet.", link="leads"))
    if attention["overdue_follow_ups"]:
        briefing.append(BriefingItem(level="action", message=f"{attention['overdue_follow_ups']} follow-up(s) for social media leads are overdue.", link="leads"))
    newest_report = (await db.execute(select(Report).where(Report.organization_id == organization_id, Report.kind == "weekly").order_by(Report.period_start.desc()).limit(1))).scalar_one_or_none()
    if newest_report is not None and (datetime.now(timezone.utc).date() - newest_report.period_end).days <= 9:
        briefing.append(BriefingItem(level="info", message=f"The weekly report for {newest_report.period_start:%d %b} to {newest_report.period_end:%d %b} is ready.", link="reports"))
    upcoming = (
        await db.execute(
            select(SocialPost.scheduled_at)
            .where(SocialPost.organization_id == organization_id, SocialPost.status == PostStatus.SCHEDULED.value)
            .order_by(SocialPost.scheduled_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if upcoming is not None:
        local = upcoming.astimezone(ZoneInfo(settings.timezone))
        briefing.append(BriefingItem(level="info", message=f"{counts.get('scheduled', 0)} post(s) scheduled. The next goes out {local.strftime('%d %b, %H:%M')} ({settings.timezone}).", link="calendar"))
    if not (settings.research_state or {}):
        briefing.append(BriefingItem(level="info", message="Research hasn't been read yet. Open Research to pull the latest CISA advisories.", link="research"))
    result = Overview(
        briefing=briefing,
        post_counts=counts,
        awaiting_approval=[PostService.public(p) for p in waiting],
        leads=leads,
        connected=connected,
        roadmap=service.roadmap(),
    )
    await db.commit()
    return result


# ---------------- settings ----------------


@router.get("/settings", response_model=SettingsPublic)
async def get_settings(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    row = await SettingsService(db).get(organization_id)
    result = SettingsPublic.model_validate(row)
    await db.commit()
    return result


@router.put("/settings", response_model=SettingsPublic)
async def update_settings(
    payload: SettingsUpdate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Brand, content pillars, personas, prohibited claims, design rules, publishing policy, budgets, notifications."""
    row = await SettingsService(db).update(organization_id, payload)
    result = SettingsPublic.model_validate(row)
    await db.commit()
    return result


# ---------------- integration ----------------


@router.get("/integration", response_model=IntegrationOverview)
async def integration(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """The connected account (if any) and an honest list of what Instagram's API offers and what is built."""
    now = datetime.now(timezone.utc)
    account = await OverviewService(db).account(organization_id)
    status_now = computed_status(account, now)
    shown = None
    if account is not None and account.token_encrypted:
        shown = AccountPublic.model_validate(account)
        shown.status = status_now
        shown.token_days_left = days_left(account, now)
    published = {
        fmt: count
        for fmt, count in (
            await db.execute(
                select(SocialPost.format, func.count()).where(
                    SocialPost.organization_id == organization_id, SocialPost.status == PostStatus.PUBLISHED.value, SocialPost.external_media_id.is_not(None)
                ).group_by(SocialPost.format)
            )
        ).all()
    }
    events = (await db.execute(select(func.count()).select_from(WebhookEvent).where(WebhookEvent.organization_id == organization_id))).scalar_one()
    proof = {
        # a real figure from Instagram (the profile counts, a daily insight or a post's insight) has been stored
        "insight_values": (await db.execute(select(func.count()).select_from(AccountDay).where(AccountDay.organization_id == organization_id))).scalar_one()
        + (await db.execute(select(func.count()).select_from(MediaMetric).where(MediaMetric.organization_id == organization_id, MediaMetric.value.is_not(None)))).scalar_one(),
        "comments": (await db.execute(select(func.count()).select_from(IgComment).where(IgComment.organization_id == organization_id))).scalar_one(),
        "conversations": (await db.execute(select(func.count()).select_from(IgConversation).where(IgConversation.organization_id == organization_id))).scalar_one(),
        "comment_replies": (await db.execute(select(func.count()).select_from(SocialReply).where(SocialReply.organization_id == organization_id, SocialReply.kind == "comment", SocialReply.status == "sent"))).scalar_one(),
        "dm_replies": (await db.execute(select(func.count()).select_from(SocialReply).where(SocialReply.organization_id == organization_id, SocialReply.kind == "dm", SocialReply.status == "sent"))).scalar_one(),
    }
    capabilities = []
    caps = (account.capabilities or {}) if account is not None else {}
    for item in defaults.CAPABILITIES:
        info = CapabilityInfo(**item)
        info.live_check = live_check(info.key, caps, status_now)
        info.verified_live = verified(info.key, status_now, published, events, proof)
        capabilities.append(info)
    return IntegrationOverview(
        account=shown,
        connected=status_now in ("connected", "expiring"),
        capabilities=capabilities,
        setup_steps=SETUP_STEPS,
        app_configured=oauth.configured(),
        redirect_uri=oauth.redirect_uri(),
        webhook_url=oauth.webhook_url(),
        webhook_verify_token_set=bool(app_settings.INSTAGRAM_WEBHOOK_VERIFY_TOKEN),
        scopes_requested=oauth.scopes(),
    )


# ---------------- posts ----------------


@router.get("/posts", response_model=PostListResponse)
async def list_posts(
    status_filter: str | None = Query(default=None, alias="status", max_length=20),
    pillar: str | None = Query(default=None, max_length=50),
    q: str | None = Query(default=None, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await PostService(db).list(organization_id, status_filter, pillar, q, skip, limit)
    return PostListResponse(items=[PostService.public(p) for p in rows], total=total)


@router.post("/posts", response_model=PostPublic, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    post = await PostService(db).create(organization_id, user.id, payload)
    result = PostService.public(post)
    await db.commit()
    return result


@router.get("/posts/{post_id}", response_model=PostPublic)
async def get_post(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    return PostService.public(await PostService(db).get(post_id, organization_id))


@router.patch("/posts/{post_id}", response_model=PostPublic)
async def update_post(
    post_id: uuid.UUID,
    payload: PostUpdate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Edit a post. Editing an approved post withdraws its approval (the response says so)."""
    service = PostService(db)
    post = await service.get(post_id, organization_id)
    if payload.verification_status is not None and payload.verification_status.value == "verified":
        # Marking claims as verified is itself a review decision, so it needs the approve permission.
        if not await _can(db, user, APPROVE):
            from app.core.exceptions import AuthorizationError

            raise AuthorizationError("Marking a post's claims as verified needs the social_media.approve permission.")
    withdrawn = await service.update(post, payload)
    result = PostService.public(post, approval_withdrawn=withdrawn)
    await db.commit()
    return result


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    service = PostService(db)
    await service.delete(await service.get(post_id, organization_id))
    await db.commit()


@router.post("/posts/{post_id}/duplicate", response_model=PostPublic, status_code=status.HTTP_201_CREATED)
async def duplicate_post(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    service = PostService(db)
    copy = await service.duplicate(await service.get(post_id, organization_id), user.id)
    result = PostService.public(copy)
    await db.commit()
    return result


@router.post("/posts/{post_id}/transition", response_model=PostPublic)
async def transition_post(
    post_id: uuid.UUID,
    payload: PostTransition,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Submit for review, request changes, approve, withdraw approval, cancel or reopen. Approving needs the
    social_media.approve permission. Publishing states can't be set here."""
    service = PostService(db)
    post = await service.get(post_id, organization_id)
    await service.transition(post, payload, user.id, can_approve=await _can(db, user, APPROVE))
    result = PostService.public(post)
    await db.commit()
    return result
