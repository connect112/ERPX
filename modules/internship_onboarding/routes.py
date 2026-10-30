"""
Internship onboarding endpoints.

Staff (``router``, mounted under /our-internships): the internship's own permissions decide who sees and changes it
(``internship_access``, so instructors keep their time-boxed rights); document review needs
``our_internships.onboarding.review`` and money needs ``our_internships.finance.*`` on top.

Students (``public_router``): no login. The link token travels in the ``X-Onboarding-Token`` header, never in the URL,
so it cannot end up in access logs. Every route is rate-limited.
"""

import uuid

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.limiter import limiter
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.internship_onboarding.config import OnboardingConfig
from modules.internship_onboarding.emails import enqueue_invitations
from modules.internship_onboarding.portal import GONE, PortalService
from modules.internship_onboarding.schemas import (
    AcceptRequest,
    ApplyTemplateRequest,
    ConfigSaveRequest,
    DecisionRequest,
    DeclineRequest,
    DraftRequest,
    LinkOut,
    ReopenRequest,
    ReviewRequest,
    StudentIdsRequest,
    TemplateArchiveRequest,
    TemplateCreateRequest,
    TemplateDuplicateRequest,
    TemplateOut,
    TemplateUpdateRequest,
)
from modules.internship_onboarding.service import ApplicationService, ConfigService, TemplateService, config_of
from modules.our_internships.access import internship_access
from modules.our_internships.models import OurInternship
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
templates_router = APIRouter()
public_router = APIRouter()


async def _internship(db: AsyncSession, internship_id: uuid.UUID, organization_id: uuid.UUID) -> OurInternship:
    from sqlalchemy import select

    row = (
        await db.execute(select(OurInternship).where(OurInternship.id == internship_id, OurInternship.organization_id == organization_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Internship", internship_id)
    return row


def _template_out(t) -> TemplateOut:
    return TemplateOut(id=t.id, name=t.name, description=t.description, version=t.version, archived=t.archived, settings=t.settings, updated_at=t.updated_at)


# ------------------------------------------------------------------ settings


@router.get("/{internship_id}/onboarding-flow/config")
async def get_config(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    return await ConfigService(db).view(await _internship(db, internship_id, organization_id), user)


@router.put("/{internship_id}/onboarding-flow/config")
async def save_config(
    internship_id: uuid.UUID,
    payload: ConfigSaveRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    await ConfigService(db).save(internship, user, payload.settings)
    return await ConfigService(db).view(internship, user)


@router.get("/{internship_id}/onboarding-flow/config/versions")
async def config_versions(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    rows = await ConfigService(db).versions(await _internship(db, internship_id, organization_id))
    return [{"version": r.version, "created_at": r.created_at, "created_by_user_id": r.created_by_user_id} for r in rows]


@router.post("/{internship_id}/onboarding-flow/apply-template")
async def apply_template(
    internship_id: uuid.UUID,
    payload: ApplyTemplateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    service = TemplateService(db)
    await service.apply(await service.get(organization_id, payload.template_id), internship, user)
    return await ConfigService(db).view(internship, user)


# ------------------------------------------------------------------ students


@router.get("/{internship_id}/onboarding-flow/dashboard")
async def dashboard(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    return await ApplicationService(db).dashboard(await _internship(db, internship_id, organization_id))


@router.get("/{internship_id}/onboarding-flow/students/{student_id}")
async def student_detail(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    return await ApplicationService(db).detail(await _internship(db, internship_id, organization_id), student_id, user)


@router.post("/{internship_id}/onboarding-flow/students/{student_id}/link", response_model=LinkOut)
async def new_link(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """A new personal link to copy and share by hand. It replaces any link sent before."""
    internship = await _internship(db, internship_id, organization_id)
    service = ApplicationService(db)
    selection, _ = await service.one(internship, student_id)
    issued = await service.issue_link(internship, selection, user.id, "copied by staff")
    return LinkOut(reference=issued.application.reference, link=issued.link)


@router.post("/{internship_id}/onboarding-flow/students/{student_id}/link/revoke")
async def revoke_link(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    service = ApplicationService(db)
    selection, _ = await service.one(internship, student_id)
    await service.revoke_link(await service.ensure(internship, selection), user.id)
    return {"message": "The link no longer works."}


@router.post("/{internship_id}/onboarding-flow/invitations", status_code=status.HTTP_202_ACCEPTED)
async def send_invitations(
    internship_id: uuid.UUID,
    payload: StudentIdsRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Email each chosen student their personal link (a new one; earlier links stop working when it is sent)."""
    internship = await _internship(db, internship_id, organization_id)
    _, config = await config_of(db, internship)
    if not config.modes.self_service:
        from app.core.exceptions import ValidationError

        raise ValidationError("Student self-service is off for this internship (manual onboarding).")
    service = ApplicationService(db)
    ids, skipped = [], []
    for selection, student in await service.selections(internship, payload.student_ids):
        if selection.offer_response.value == "declined":
            skipped.append({"name": student.name, "reason": "Declined the offer."})
            continue
        application = await service.ensure(internship, selection, config)
        ids.append(application.id)
    await db.commit()  # the worker reads the applications
    enqueue_invitations(ids)
    return {"queued": len(ids), "skipped": skipped}


@router.post("/{internship_id}/onboarding-flow/reopen")
async def reopen(
    internship_id: uuid.UUID,
    payload: ReopenRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    return await ApplicationService(db).reopen(
        internship, payload.student_ids, payload.until, payload.reason, payload.late_fee, payload.late_fee_amount, user
    )


@router.post("/{internship_id}/onboarding-flow/students/{student_id}/info-review")
async def review_info(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: DecisionRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    await ApplicationService(db).review_info(await _internship(db, internship_id, organization_id), student_id, payload.approve, user)
    return {"message": "Applied." if payload.approve else "Turned down."}


@router.get("/{internship_id}/onboarding-flow/documents/{document_id}/preview")
async def preview_document(
    internship_id: uuid.UUID,
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    url = await ApplicationService(db).preview_url(await _internship(db, internship_id, organization_id), document_id, user)
    return {"url": url}


@router.post("/{internship_id}/onboarding-flow/documents/{document_id}/review")
async def review_document(
    internship_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: ReviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    document = await ApplicationService(db).review(await _internship(db, internship_id, organization_id), document_id, payload.approve, payload.note, user)
    return {"id": document.id, "status": document.status}


# ------------------------------------------------------------------ templates


@templates_router.get("", response_model=list[TemplateOut])
async def list_templates(
    include_archived: bool = False,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    return [_template_out(t) for t in await TemplateService(db).list(organization_id, include_archived)]


@templates_router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: TemplateCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.settings
    if payload.from_internship_id is not None:
        _, config = await config_of(db, await _internship(db, payload.from_internship_id, organization_id))
        data = config.model_dump(mode="json")
    return _template_out(await TemplateService(db).create(organization_id, user, payload.name, payload.description, data or OnboardingConfig().model_dump(mode="json")))


@templates_router.patch("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TemplateService(db)
    return _template_out(await service.update(await service.get(organization_id, template_id), user, payload.name, payload.description, payload.settings))


@templates_router.post("/{template_id}/duplicate", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def duplicate_template(
    template_id: uuid.UUID,
    payload: TemplateDuplicateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TemplateService(db)
    return _template_out(await service.duplicate(await service.get(organization_id, template_id), user, payload.name))


@templates_router.post("/{template_id}/archive", response_model=TemplateOut)
async def archive_template(
    template_id: uuid.UUID,
    payload: TemplateArchiveRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TemplateService(db)
    return _template_out(await service.archive(await service.get(organization_id, template_id), payload.archived))


# ------------------------------------------------------------------ students (public, by link)


async def _context(db: AsyncSession, token: str | None):
    try:
        return await PortalService(db).resolve(token or "")
    except NotFoundError:
        raise NotFoundError("Onboarding link", "") from None


@public_router.get("/internship-onboarding")
@limiter.limit("60/minute")
async def portal_view(request: Request, x_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    service = PortalService(db)
    return await service.view(await _context(db, x_onboarding_token))


@public_router.put("/internship-onboarding/draft")
@limiter.limit("30/minute")
async def portal_save(
    request: Request, payload: DraftRequest, x_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db),
):
    service = PortalService(db)
    return await service.save(await _context(db, x_onboarding_token), payload.step, payload.info, payload.answers)


@public_router.post("/internship-onboarding/documents/{key}", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def portal_upload(
    request: Request, key: str, file: UploadFile = File(...), x_onboarding_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    from modules.internship_onboarding.config import MAX_DOCUMENT_MB

    ctx = await _context(db, x_onboarding_token)
    data = await file.read(MAX_DOCUMENT_MB * 1024 * 1024 + 1)
    document = await PortalService(db).upload(ctx, key, file.filename or "document", data)
    return {"key": document.requirement_key, "version": document.version, "status": document.status, "filename": document.filename}


@public_router.post("/internship-onboarding/accept")
@limiter.limit("10/minute")
async def portal_accept(
    request: Request, payload: AcceptRequest, x_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db),
):
    service = PortalService(db)
    ctx = await _context(db, x_onboarding_token)
    await service.accept(ctx, payload.confirmed, payload.terms_version, request.client.host if request.client else None, request.headers.get("User-Agent"))
    return await service.view(ctx)


@public_router.post("/internship-onboarding/decline")
@limiter.limit("10/minute")
async def portal_decline(
    request: Request, payload: DeclineRequest, x_onboarding_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db),
):
    service = PortalService(db)
    ctx = await _context(db, x_onboarding_token)
    await service.decline(ctx, payload.reason)
    return await service.view(ctx)


__all__ = ["router", "templates_router", "public_router", "GONE"]
