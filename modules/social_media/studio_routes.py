"""Research, the content studio, automated checks, content history and AI usage."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.social_media import image_provider
from modules.social_media.checks import check_and_store
from modules.social_media.history import HistoryService
from modules.social_media.research import SOURCE_LABELS, ResearchService, SourceUnavailable
from modules.social_media.schemas import (
    CveLookup,
    GenerateRequest,
    HistoryOverview,
    PillarBalanceOut,
    PostPublic,
    RefreshResult,
    RegenerateRequest,
    ResearchItemPublic,
    ResearchListResponse,
    UsageOverview,
)
from modules.social_media.service import PostService, SettingsService
from modules.social_media.studio import ContentStudio
from modules.social_media.usage import UsageService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

VIEW = "social_media.view"
MANAGE = "social_media.manage"


# ---------------- research ----------------


@router.get("/research", response_model=ResearchListResponse)
async def list_research(
    source: str | None = Query(default=None, pattern=r"^(cisa_kev|cisa_advisory)$"),
    status_filter: str | None = Query(default=None, alias="status", pattern=r"^(new|used|dismissed)$"),
    q: str | None = Query(default=None, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """What the official sources have said recently (retrieved and cached), and when each source was last read."""
    settings = await SettingsService(db).get(organization_id)
    rows, total = await ResearchService(db).list(organization_id, source, status_filter, q, skip, limit)
    state = settings.research_state or {}
    sources = {key: {"label": label, **(state.get(key) or {})} for key, label in SOURCE_LABELS.items() if key != "nvd"}
    result = ResearchListResponse(items=[ResearchItemPublic.model_validate(r) for r in rows], total=total, sources=sources)
    await db.commit()
    return result


@router.post("/research/refresh", response_model=list[RefreshResult])
async def refresh_research(
    force: bool = Query(default=False),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Read CISA's feeds now (each at most every few hours unless forced). A source that can't be reached is reported,
    never filled in."""
    settings = await SettingsService(db).get(organization_id)
    results = await ResearchService(db).refresh(organization_id, settings, force=force)
    await db.commit()
    return [RefreshResult(**r) for r in results]


@router.post("/research/cve", response_model=ResearchItemPublic)
async def look_up_cve(
    payload: CveLookup,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Look one CVE up in the National Vulnerability Database (so a post about it can be built on verified facts)."""
    try:
        item = await ResearchService(db).lookup_cve(organization_id, payload.cve)
    except SourceUnavailable as exc:
        raise ServiceUnavailableError(f"NVD couldn't be checked right now: {exc}") from None
    if item is None:
        raise NotFoundError("NVD has no record of that CVE identifier.")
    result = ResearchItemPublic.model_validate(item)
    await db.commit()
    return result


@router.post("/research/{item_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_research(
    item_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    item = await ResearchService(db).get(organization_id, item_id)
    if item is None:
        raise NotFoundError("Research item not found.")
    item.status = "dismissed"
    await db.commit()


# ---------------- studio ----------------


@router.post("/studio/generate", response_model=PostPublic, status_code=status.HTTP_201_CREATED)
async def generate_draft(
    payload: GenerateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Draft a post with AI from the brand strategy and the selected research. The result is always a DRAFT: nothing is
    approved, scheduled or published. It is checked automatically and then needs a person's review."""
    settings = await SettingsService(db).get(organization_id)
    post = await ContentStudio(db).generate(
        organization_id,
        user.id,
        settings,
        topic=payload.topic.strip(),
        post_format=payload.format.value,
        pillar=payload.pillar,
        persona_key=payload.persona_key,
        research_item_ids=payload.research_item_ids,
        notes=payload.notes.strip(),
        time_sensitive=payload.time_sensitive,
    )
    result = PostService.public(post)
    await db.commit()
    return result


@router.post("/posts/{post_id}/regenerate", response_model=PostPublic)
async def regenerate_element(
    post_id: uuid.UUID,
    payload: RegenerateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Rewrite one element of a post (its hooks, headline, caption ...) without touching the rest."""
    settings = await SettingsService(db).get(organization_id)
    post = await PostService(db).get(post_id, organization_id)
    withdrawn = await ContentStudio(db).regenerate(organization_id, user.id, settings, post, payload.element, payload.instruction.strip())
    result = PostService.public(post, approval_withdrawn=withdrawn)
    await db.commit()
    return result


@router.post("/posts/{post_id}/check", response_model=PostPublic)
async def run_post_checks(
    post_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Run the automated checks again (CVE facts against NVD, sources, claims, design limits, history)."""
    settings = await SettingsService(db).get(organization_id)
    post = await PostService(db).get(post_id, organization_id)
    await check_and_store(db, organization_id, post, settings)
    await db.refresh(post)
    result = PostService.public(post)
    await db.commit()
    return result


# ---------------- history and usage ----------------


@router.get("/history", response_model=HistoryOverview)
async def content_history(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """The mix of topics in recent posts against the targets, and what to cover next."""
    settings = await SettingsService(db).get(organization_id)
    history = HistoryService(db)
    balance = await history.balance(organization_id, settings)
    considered = len(await history.recent(organization_id, limit=20))
    result = HistoryOverview(
        pillars=[PillarBalanceOut(key=b.key, label=b.label, target=b.target, actual=b.actual, recent=b.recent) for b in balance],
        posts_considered=considered,
        suggestions=history.suggestions(balance, considered),
    )
    await db.commit()
    return result


@router.get("/usage", response_model=UsageOverview)
async def ai_usage(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """This month's estimated AI cost against the budget."""
    settings = await SettingsService(db).get(organization_id)
    summary = await UsageService(db).summary(organization_id, settings)
    result = UsageOverview(**summary, ai_configured=bool(app_settings.AI_API_KEY), image_configured=image_provider.configured())
    await db.commit()
    return result
