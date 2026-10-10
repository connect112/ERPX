"""Tracked links, turning enquiries into CRM leads (by a person), and the enquiry-to-enrolment report.

Permissions: seeing the report and the links needs `social_media.view`; making or pausing a link needs `social_media.manage`;
creating a lead from a comment or message needs `social_media.inbox` AND the CRM's own `crm.leads.manage` (a follow-up also needs
`crm.followups.manage`); the list of linked leads also needs `crm.leads.view`. The one public address is the tracked-link redirect."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.core.limiter import limiter
from app.db.session import get_db
from modules.authentication.models import User, UserStatus
from modules.authorization.dependencies import require_permissions
from modules.authorization.repository import AuthorizationRepository
from modules.courses.models import Course
from modules.crm.leads.models import Lead
from modules.marketing.campaigns.models import Campaign
from modules.social_media import hashtags
from modules.social_media.attribution import AttributionService
from modules.social_media.inbox import InboxService
from modules.social_media.leads import SocialLeadService, suggest_course
from modules.social_media.links import LinkService, is_robot, recent_window, short_url, target_url
from modules.social_media.models import LeadLink, TrackedLink
from modules.social_media.schemas import LeadCreated, LeadFromInbox, LinkCreate, LinkOut, LinkUpdate
from modules.users.dependencies import get_current_user_organization_id
from modules.users.models import UserProfile

router = APIRouter()

VIEW = "social_media.view"
MANAGE = "social_media.manage"
INBOX = "social_media.inbox"
LEADS_MANAGE = "crm.leads.manage"
LEADS_VIEW = "crm.leads.view"
FOLLOWUPS_MANAGE = "crm.followups.manage"


def _link_out(link: TrackedLink, clicks_total: int = 0, clicks_28d: int = 0, last_click_day=None) -> LinkOut:
    return LinkOut(
        id=link.id, name=link.name, token=link.token, short_url=short_url(link.token), final_url=target_url(link), destination=link.destination, placement=link.placement, post_id=link.post_id,
        course_label=link.course_label, marketing_campaign_id=link.marketing_campaign_id, utm_campaign=link.utm_campaign, utm_content=link.utm_content, is_active=link.is_active,
        created_at=link.created_at, clicks_total=clicks_total, clicks_28d=clicks_28d, last_click_day=last_click_day,
    )


# ---------------- the public redirect ----------------


@router.get("/l/{token}", include_in_schema=False)
@limiter.limit("120/minute")
async def open_tracked_link(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Count one open (robots and previews excluded) and send the visitor on. Public: no login."""
    if len(token) > 20:
        return PlainTextResponse("This link isn't available.", status_code=404)
    service = LinkService(db)
    if is_robot(request.headers.get("user-agent")):
        link = (await db.execute(select(TrackedLink).where(TrackedLink.token == token, TrackedLink.is_active.is_(True)))).scalar_one_or_none()
        url = target_url(link) if link else None
    else:
        url = await service.record_click(token)
        await db.commit()
    if url is None:
        return PlainTextResponse("This link isn't available.", status_code=404)
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})


# ---------------- links ----------------


@router.get("/links", response_model=list[LinkOut])
async def list_links(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    return [_link_out(s["link"], s["clicks_total"], s["clicks_28d"], s["last_click_day"]) for s in await LinkService(db).stats(organization_id)]


@router.post("/links", response_model=LinkOut, status_code=201)
async def create_link(
    payload: LinkCreate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    link = await LinkService(db).create(organization_id, user.id, payload.model_dump())
    result = _link_out(link)
    await db.commit()
    return result


@router.patch("/links/{link_id}", response_model=LinkOut)
async def update_link(
    link_id: uuid.UUID,
    payload: LinkUpdate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    service = LinkService(db)
    link = await service.update(organization_id, link_id, payload.model_dump(exclude_unset=True))
    stats = next((s for s in await service.stats(organization_id) if s["link"].id == link.id), None)
    result = _link_out(link, stats["clicks_total"] if stats else 0, stats["clicks_28d"] if stats else 0, stats["last_click_day"] if stats else None)
    await db.commit()
    return result


# ---------------- leads ----------------


@router.get("/leads/options")
async def lead_options(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX, LEADS_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """What the create-lead form offers: published courses, marketing campaigns and the team."""
    courses = (await db.execute(select(Course.id, Course.title).where(Course.organization_id == organization_id, Course.is_published.is_(True), Course.deleted_at.is_(None)).order_by(Course.title))).all()
    campaigns = (await db.execute(select(Campaign.id, Campaign.name).where(Campaign.organization_id == organization_id).order_by(Campaign.created_at.desc()).limit(100))).all()
    team = (
        await db.execute(
            select(User.id, User.full_name).join(UserProfile, UserProfile.user_id == User.id).where(UserProfile.organization_id == organization_id, User.status == UserStatus.ACTIVE, User.deleted_at.is_(None)).order_by(User.full_name)
        )
    ).all()
    return {
        "courses": [{"id": i, "title": t} for i, t in courses],
        "campaigns": [{"id": i, "name": n} for i, n in campaigns],
        "team": [{"id": i, "name": n} for i, n in team],
    }


async def _hint(db: AsyncSession, organization_id: uuid.UUID, text: str, comment_id=None, conversation_id=None) -> dict:
    existing = None
    if comment_id is not None:
        existing = (await db.execute(select(LeadLink.lead_id).where(LeadLink.comment_id == comment_id))).scalar_one_or_none()
    if conversation_id is not None:
        existing = (await db.execute(select(LeadLink.lead_id).where(LeadLink.conversation_id == conversation_id))).scalar_one_or_none()
    return {"existing_lead_id": existing, "suggested_course": await suggest_course(db, organization_id, text)}


@router.get("/comments/{comment_id}/lead-hint")
async def comment_lead_hint(
    comment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    comment = await InboxService(db).get_comment(organization_id, comment_id)
    return {**await _hint(db, organization_id, comment.text, comment_id=comment.id), "default_name": comment.author_username or ""}


@router.get("/conversations/{conversation_id}/lead-hint")
async def conversation_lead_hint(
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    inbox = InboxService(db)
    conversation = await inbox.get_conversation(organization_id, conversation_id)
    messages = await inbox.messages(conversation.id)
    text = " ".join(m.text or "" for m in messages if m.direction == "in")
    return {**await _hint(db, organization_id, text, conversation_id=conversation.id), "default_name": conversation.participant_username or ""}


async def _needs_followup_permission(db: AsyncSession, user: User, payload: LeadFromInbox) -> None:
    if payload.follow_up is not None and not user.is_superuser and FOLLOWUPS_MANAGE not in await AuthorizationRepository(db).get_permission_codes_for_user(user.id):
        raise AuthorizationError(f"Scheduling a follow-up requires the {FOLLOWUPS_MANAGE} permission.")


@router.post("/comments/{comment_id}/lead", response_model=LeadCreated, status_code=201)
async def lead_from_comment(
    comment_id: uuid.UUID,
    payload: LeadFromInbox,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX, LEADS_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """A team member decides this comment is a genuine enquiry and creates the CRM lead. Never automatic."""
    await _needs_followup_permission(db, user, payload)
    comment = await InboxService(db).get_comment(organization_id, comment_id)
    data = payload.model_dump()
    result = await SocialLeadService(db).from_comment(organization_id, user, comment, data)
    await db.commit()
    return result


@router.post("/conversations/{conversation_id}/lead", response_model=LeadCreated, status_code=201)
async def lead_from_conversation(
    conversation_id: uuid.UUID,
    payload: LeadFromInbox,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX, LEADS_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    await _needs_followup_permission(db, user, payload)
    conversation = await InboxService(db).get_conversation(organization_id, conversation_id)
    result = await SocialLeadService(db).from_conversation(organization_id, user, conversation, payload.model_dump())
    await db.commit()
    return result


@router.get("/leads/funnel")
async def funnel(
    days: int = Query(default=28, ge=7, le=90),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    start, end = recent_window(days)
    return await AttributionService(db).funnel(organization_id, start, end)


@router.get("/leads/people")
async def linked_leads(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW, LEADS_VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """The leads a team member created from social media, how each is going, and which need a first contact or a follow-up."""
    return {"items": await AttributionService(db).social_leads(organization_id)}


# ---------------- hashtags ----------------


@router.get("/analytics/hashtags")
async def hashtag_report(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    return await hashtags.report(db, organization_id)
