import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.authorization.repository import AuthorizationRepository
from modules.social_media import defaults
from modules.social_media.models import PostStatus
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
from modules.social_media.studio_routes import router as studio_router
from modules.social_media.usage import UsageService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
router.include_router(studio_router)
router.include_router(art_router)

VIEW = "social_media.view"
MANAGE = "social_media.manage"
APPROVE = "social_media.approve"

SETUP_STEPS = [
    "Make sure the Instagram account is a Professional account (Business or Creator).",
    "Create a Meta developer app and add the Instagram product (developers.facebook.com/docs/instagram-platform).",
    "Add the Instagram account as a tester, then request the permissions you need; messaging, comments and publishing "
    "for accounts other than your own testers need Meta app review.",
    "Set the app's redirect and webhook URLs to this site (shown here once the connection is built).",
    "Connect from this page (Phase 4). Tokens will be stored encrypted on the server and never sent to the browser.",
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
    connected = account is not None and account.status in ("connected", "expiring")
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
    account = await OverviewService(db).account(organization_id)
    return IntegrationOverview(
        account=AccountPublic.model_validate(account) if account else None,
        connected=account is not None and account.status in ("connected", "expiring"),
        capabilities=[CapabilityInfo(**item) for item in defaults.CAPABILITIES],
        setup_steps=SETUP_STEPS,
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
