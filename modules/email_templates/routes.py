"""
Editing the emails ERPX sends.

Two sets of endpoints share one implementation: the organisation-wide editor under
`/email-templates` (the admin section), and the per-event editor under
`/hackathons/{hackathon_id}/email-templates` (the hackathon page; only emails that belong to events).
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.email_templates.schemas import (
    PreviewRequest,
    PreviewResponse,
    TemplateDetail,
    TemplateSaveRequest,
    TemplateSummary,
    TestSendRequest,
    TestSendResponse,
)
from modules.email_templates.service import EmailTemplateService
from modules.hackathons.service import HackathonService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()  # /email-templates
event_router = APIRouter()  # /hackathons/{hackathon_id}/email-templates


async def _event_service(db: AsyncSession, organization_id: uuid.UUID, hackathon_id: uuid.UUID) -> EmailTemplateService:
    await HackathonService(db).get_hackathon(hackathon_id, organization_id)  # 404 unless it is this organisation's
    return EmailTemplateService(db, organization_id, hackathon_id)


# ---------------- organisation-wide ----------------


@router.get("", response_model=list[TemplateSummary])
async def list_templates(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("email_templates.view")),
    db: AsyncSession = Depends(get_db),
):
    return await EmailTemplateService(db, organization_id).list_all()


@router.get("/{key}", response_model=TemplateDetail)
async def get_template(
    key: str,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("email_templates.view")),
    db: AsyncSession = Depends(get_db),
):
    return await EmailTemplateService(db, organization_id).detail(key)


@router.put("/{key}", response_model=TemplateDetail)
async def save_template(
    key: str,
    payload: TemplateSaveRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("email_templates.manage")),
    db: AsyncSession = Depends(get_db),
):
    return await EmailTemplateService(db, organization_id).save(key, payload.subject, payload.body, user.id)


@router.delete("/{key}", response_model=TemplateDetail)
async def reset_template(
    key: str,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("email_templates.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Throw away the edits: the built-in default wording is used again."""
    return await EmailTemplateService(db, organization_id).reset(key)


@router.post("/{key}/preview", response_model=PreviewResponse)
async def preview_template(
    key: str,
    payload: PreviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("email_templates.view")),
    db: AsyncSession = Depends(get_db),
):
    return EmailTemplateService(db, organization_id).preview(key, payload.subject, payload.body)


@router.post("/{key}/test", response_model=TestSendResponse)
async def send_test_email(
    key: str,
    payload: TestSendRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("email_templates.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Send this wording (the draft in the editor, or the saved one) with sample values to one address."""
    sent, message = await EmailTemplateService(db, organization_id).send_test(
        key, str(payload.to_email), user.id, payload.subject, payload.body
    )
    return TestSendResponse(sent=sent, message=message)


# ---------------- one hackathon ----------------


@event_router.get("/{hackathon_id}/email-templates", response_model=list[TemplateSummary])
async def list_event_templates(
    hackathon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    return await (await _event_service(db, organization_id, hackathon_id)).list_all()


@event_router.get("/{hackathon_id}/email-templates/{key}", response_model=TemplateDetail)
async def get_event_template(
    hackathon_id: uuid.UUID,
    key: str,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    return await (await _event_service(db, organization_id, hackathon_id)).detail(key)


@event_router.put("/{hackathon_id}/email-templates/{key}", response_model=TemplateDetail)
async def save_event_template(
    hackathon_id: uuid.UUID,
    key: str,
    payload: TemplateSaveRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    return await (await _event_service(db, organization_id, hackathon_id)).save(key, payload.subject, payload.body, user.id)


@event_router.delete("/{hackathon_id}/email-templates/{key}", response_model=TemplateDetail)
async def reset_event_template(
    hackathon_id: uuid.UUID,
    key: str,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Drop this event's own wording: it goes back to the organisation's (or the built-in default)."""
    return await (await _event_service(db, organization_id, hackathon_id)).reset(key)


@event_router.post("/{hackathon_id}/email-templates/{key}/preview", response_model=PreviewResponse)
async def preview_event_template(
    hackathon_id: uuid.UUID,
    key: str,
    payload: PreviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    return (await _event_service(db, organization_id, hackathon_id)).preview(key, payload.subject, payload.body)


@event_router.post("/{hackathon_id}/email-templates/{key}/test", response_model=TestSendResponse)
async def send_event_test_email(
    hackathon_id: uuid.UUID,
    key: str,
    payload: TestSendRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hackathons.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = await _event_service(db, organization_id, hackathon_id)
    sent, message = await service.send_test(key, str(payload.to_email), user.id, payload.subject, payload.body)
    return TestSendResponse(sent=sent, message=message)
