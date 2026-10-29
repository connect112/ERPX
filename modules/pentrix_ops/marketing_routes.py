"""
Pentrix marketing email API (`/pentrix-ops/marketing`) and the public unsubscribe page's API (`/public/pentrix-marketing`).

Viewing the templates and the campaigns needs `pentrix_ops.marketing.view`; choosing which templates may be used and when needs
`pentrix_ops.marketing.manage`; previewing recipients, previewing the email and confirming a send need `pentrix_ops.marketing.send`.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.pentrix_ops.marketing import REASON_LABEL, PentrixMarketingService
from modules.pentrix_ops.marketing_schemas import (
    AssignableOut,
    CampaignCreate,
    CampaignOut,
    CampaignPage,
    CampaignPreviewIn,
    EmailPreviewOut,
    ExcludedOut,
    MarketingTemplateOut,
    OptionsOut,
    PersonOut,
    RecipientOut,
    RecipientPage,
    RecipientsPreviewIn,
    RecipientsPreviewOut,
    TemplateAssign,
    TemplateUpdate,
    UnsubscribeInfo,
)
from modules.pentrix_ops.routes import _scope
from modules.pentrix_ops.schemas import MessageOut
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
public_router = APIRouter()

View = Depends(require_permissions("pentrix_ops.marketing.view"))
Manage = Depends(require_permissions("pentrix_ops.marketing.manage"))
Send = Depends(require_permissions("pentrix_ops.marketing.send"))
Org = Depends(get_current_user_organization_id)
Db = Depends(get_db)

PEOPLE_SHOWN = 50


def _recipients_out(resolution) -> RecipientsPreviewOut:
    return RecipientsPreviewOut(
        selected=resolution.selected,
        eligible=len(resolution.eligible),
        excluded=[ExcludedOut(reason=k, label=REASON_LABEL[k], count=v) for k, v in resolution.excluded.items()],
        people=[PersonOut(id=c.id, name=c.full_name, email=c.email) for c in resolution.eligible[:PEOPLE_SHOWN]],
        people_shown=min(len(resolution.eligible), PEOPLE_SHOWN),
    )


# ------------------------------------------------------------------ the templates made available for it


@router.get("/templates", response_model=list[MarketingTemplateOut])
async def list_templates(
    usable: bool = Query(default=False, description="only those that can be sent on that date"),
    on: date | None = Query(default=None, description="the campaign date (default today)"),
    category: str | None = Query(default=None, max_length=60),
    q: str | None = Query(default=None, max_length=100),
    organization_id: uuid.UUID = Org,
    user: User = View,
    db: AsyncSession = Db,
):
    await _scope(organization_id, db)
    return await PentrixMarketingService(db).templates(organization_id, on=on, usable_only=usable, category=category, q=q)


@router.get("/templates/assignable", response_model=list[AssignableOut])
async def assignable_templates(organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    return await PentrixMarketingService(db).assignable(organization_id)


@router.post("/templates", response_model=MarketingTemplateOut, status_code=201)
async def assign_template(payload: TemplateAssign, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    return await PentrixMarketingService(db).assign(organization_id, user.id, payload.template_id, payload.campaign_name, payload.available_from, payload.available_until)


@router.patch("/templates/{assignment_id}", response_model=MarketingTemplateOut)
async def update_template(assignment_id: uuid.UUID, payload: TemplateUpdate, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise ValidationError("Nothing to change.")
    return await PentrixMarketingService(db).update_assignment(organization_id, assignment_id, changes)


@router.delete("/templates/{assignment_id}", response_model=MessageOut)
async def remove_template(assignment_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await _scope(organization_id, db)
    await PentrixMarketingService(db).remove_assignment(organization_id, assignment_id)
    return MessageOut(message="Removed. The template itself is untouched in Email Studio.")


@router.get("/options", response_model=OptionsOut)
async def brand_and_signature_options(organization_id: uuid.UUID = Org, user: User = Send, db: AsyncSession = Db):
    await _scope(organization_id, db)
    return await PentrixMarketingService(db).options(organization_id)


# ------------------------------------------------------------------ choosing people and previewing


@router.post("/recipients/preview", response_model=RecipientsPreviewOut)
async def preview_recipients(payload: RecipientsPreviewIn, organization_id: uuid.UUID = Org, user: User = Send, db: AsyncSession = Db):
    """Who would receive it, and for each person left out, why. Nothing is sent."""
    await _scope(organization_id, db)
    service = PentrixMarketingService(db)
    template_id = None
    if payload.assignment_id:
        _, template, _ = await service.usable_assignment(organization_id, payload.assignment_id)
        template_id = template.id
    return _recipients_out(await service.resolve(organization_id, payload.selection.as_dict(), template_id))


@router.post("/preview", response_model=EmailPreviewOut)
async def preview_email(payload: CampaignPreviewIn, organization_id: uuid.UUID = Org, user: User = Send, db: AsyncSession = Db):
    """The email as a candidate (or a sample) would receive it: subject, resolved content, brand, signature, attachments and, when a
    selection is given, the recipient count. Nothing is sent."""
    await _scope(organization_id, db)
    service = PentrixMarketingService(db)
    resolution = None
    candidate_id = payload.candidate_id
    if payload.selection is not None:
        _, template, _ = await service.usable_assignment(organization_id, payload.assignment_id)
        resolution = await service.resolve(organization_id, payload.selection.as_dict(), template.id)
        if candidate_id is None and resolution.eligible:
            candidate_id = resolution.eligible[0].id
    preview = await service.preview(organization_id, payload.assignment_id, candidate_id=candidate_id, brand_profile_id=payload.brand_profile_id, signature_id=payload.signature_id)
    return EmailPreviewOut(**preview, recipients=_recipients_out(resolution) if resolution else None)


# ------------------------------------------------------------------ sending and tracking


@router.post("/campaigns", response_model=CampaignOut, status_code=201)
async def confirm_send(payload: CampaignCreate, organization_id: uuid.UUID = Org, user: User = Send, db: AsyncSession = Db):
    """The explicit confirmation. The people are chosen again here; if that is not the number that was shown, nothing is sent."""
    await _scope(organization_id, db)
    service = PentrixMarketingService(db)
    campaign = await service.create_campaign(
        organization_id, user.id, payload.assignment_id, payload.selection.as_dict(), expected_count=payload.expected_count,
        brand_profile_id=payload.brand_profile_id, signature_id=payload.signature_id, idempotency_key=payload.idempotency_key,
    )
    return CampaignOut(**service.campaign_out(campaign, (await service.counts([campaign.id]))[campaign.id]))


@router.get("/campaigns", response_model=CampaignPage)
async def list_campaigns(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    await _scope(organization_id, db)
    items, total = await PentrixMarketingService(db).campaigns(organization_id, page, page_size)
    return CampaignPage(items=[CampaignOut(**i) for i in items], total=total, page=page, page_size=page_size)


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
async def get_campaign(campaign_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    await _scope(organization_id, db)
    service = PentrixMarketingService(db)
    campaign = await service.campaign(organization_id, campaign_id)
    return CampaignOut(**service.campaign_out(campaign, (await service.counts([campaign.id]))[campaign.id]))


@router.get("/campaigns/{campaign_id}/recipients", response_model=RecipientPage)
async def campaign_recipients(
    campaign_id: uuid.UUID, status: str | None = Query(default=None, pattern="^(queued|sending|sent|delivered|failed|bounced|skipped)$"),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db,
):
    await _scope(organization_id, db)
    rows, total = await PentrixMarketingService(db).recipients(organization_id, campaign_id, status, page, page_size)
    return RecipientPage(items=[RecipientOut.model_validate(r, from_attributes=True) for r in rows], total=total, page=page, page_size=page_size)


@router.post("/campaigns/{campaign_id}/cancel", response_model=CampaignOut)
async def cancel_campaign(campaign_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Send, db: AsyncSession = Db):
    """Stop a send that is still going. Messages already sent cannot be taken back; those still waiting are not sent."""
    await _scope(organization_id, db)
    service = PentrixMarketingService(db)
    campaign = await service.cancel(organization_id, campaign_id)
    return CampaignOut(**service.campaign_out(campaign, (await service.counts([campaign.id]))[campaign.id]))


# ------------------------------------------------------------------ public: the unsubscribe link (no sign-in)


@public_router.get("/unsubscribe", response_model=UnsubscribeInfo)
async def unsubscribe_info(token: str = Query(max_length=600), db: AsyncSession = Db):
    """Whose address the link is for (masked), so the page can ask "unsubscribe jo***@example.com?"."""
    return UnsubscribeInfo(**PentrixMarketingService(db).check_token(token))


@public_router.post("/unsubscribe", response_model=UnsubscribeInfo)
async def unsubscribe(request: Request, token: str = Query(max_length=600), db: AsyncSession = Db):
    """Unsubscribe. Takes effect at once and is harmless to repeat. Also the target of the one-click List-Unsubscribe header, which mail
    programs POST to without a person looking at a page."""
    return UnsubscribeInfo(**await PentrixMarketingService(db).unsubscribe(token))
