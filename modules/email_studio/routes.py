"""
Email Studio API (`/email-studio`).

Viewing and previewing needs `email_templates.view`; creating, editing and test sends need `email_templates.manage`; publishing a
version, using a template for an ERPX email, and approving a signature image need `email_templates.publish`. Every check is made
here on the server; the screens only hide what a person cannot use.
"""

import uuid

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.email_studio.branding import BrandingService
from modules.email_studio.models import EmailAsset, EmailSendRecord, EmailStudioTemplate, EmailStudioVersion
from modules.email_studio.schemas import (
    CATEGORIES,
    ApproveSignatureRequest,
    AssetOut,
    AssignRequest,
    BrandOut,
    BrandPayload,
    CodeTemplateOut,
    ComponentOut,
    ComponentPayload,
    CreatePayload,
    DraftOut,
    DraftPayload,
    HistoryItem,
    LibraryItem,
    MessageOut,
    PlaceholderOut,
    PreviewRequest,
    PreviewResponse,
    SignatureOut,
    SignaturePayload,
    TemplateOut,
    TestRequest,
    TestResponse,
    VersionOut,
)
from modules.email_studio.service import StudioService, catalog, code_templates_out
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
public_router = APIRouter()

_IMAGE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "Cache-Control": "public, max-age=86400",
    "Cross-Origin-Resource-Policy": "cross-origin",
}

View = Depends(require_permissions("email_templates.view"))
Manage = Depends(require_permissions("email_templates.manage"))
Publish = Depends(require_permissions("email_templates.publish"))
Org = Depends(get_current_user_organization_id)
Db = Depends(get_db)


# ------------------------------------------------------------------ the library


@router.get("/library", response_model=list[LibraryItem])
async def library(organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    """Every email: the ones designed in Email Studio and the built-in ERPX emails (with how each is currently made)."""
    return await StudioService(db, organization_id).library()


@router.get("/categories", response_model=list[str])
async def categories(user: User = View):
    return list(CATEGORIES)


@router.get("/placeholders", response_model=list[PlaceholderOut])
async def placeholders(key: str | None = Query(default=None), user: User = View):
    """The placeholders that can be inserted, grouped (for one ERPX email, only the values it supplies)."""
    return catalog(key)


@router.get("/code-templates", response_model=list[CodeTemplateOut])
async def code_templates(user: User = View):
    """The React Email components that were reviewed and approved by a developer."""
    return code_templates_out()


# ------------------------------------------------------------------ templates


@router.post("/templates", response_model=TemplateOut, status_code=201)
async def create_template(payload: CreatePayload, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    return await StudioService(db, organization_id).create(payload, user.id)


@router.get("/templates/{template_id}", response_model=TemplateOut)
async def get_template(template_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    service = StudioService(db, organization_id)
    return await service.out(await service.template(template_id))


@router.put("/templates/{template_id}/draft", response_model=TemplateOut)
async def save_draft(template_id: uuid.UUID, payload: DraftPayload, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    """Save the editor's work as the draft. It changes nothing that is sent until it is published."""
    service = StudioService(db, organization_id)
    return await service.save_draft(await service.template(template_id), payload, user.id)


@router.delete("/templates/{template_id}/draft", response_model=TemplateOut)
async def discard_draft(template_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    service = StudioService(db, organization_id)
    return await service.discard_draft(await service.template(template_id))


@router.post("/templates/{template_id}/publish", response_model=TemplateOut)
async def publish_template(template_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Publish, db: AsyncSession = Db):
    service = StudioService(db, organization_id)
    return await service.publish(await service.template(template_id), user.id)


@router.delete("/templates/{template_id}", response_model=MessageOut)
async def delete_template(template_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    """Delete a template you made (never a built-in ERPX email). Refused while an ERPX email uses it."""
    service = StudioService(db, organization_id)
    await service.delete(await service.template(template_id))
    return MessageOut(message="Deleted.")


@router.post("/templates/{template_id}/duplicate", response_model=TemplateOut, status_code=201)
async def duplicate_template(template_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    service = StudioService(db, organization_id)
    return await service.duplicate(await service.template(template_id), user.id)


@router.post("/templates/{template_id}/archive", response_model=TemplateOut)
async def archive_template(template_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    service = StudioService(db, organization_id)
    return await service.archive(await service.template(template_id), True, user.id)


@router.post("/templates/{template_id}/unarchive", response_model=TemplateOut)
async def unarchive_template(template_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    service = StudioService(db, organization_id)
    return await service.archive(await service.template(template_id), False, user.id)


@router.get("/templates/{template_id}/versions", response_model=list[VersionOut])
async def versions(template_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    service = StudioService(db, organization_id)
    return await service.versions(await service.template(template_id))


@router.get("/templates/{template_id}/versions/{version_id}", response_model=DraftOut)
async def get_version(template_id: uuid.UUID, version_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    service = StudioService(db, organization_id)
    return await service.version_out(await service.template(template_id), version_id)


@router.post("/templates/{template_id}/versions/{version_id}/restore", response_model=TemplateOut)
async def restore_version(template_id: uuid.UUID, version_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    """Make an earlier version the draft. Nothing changes for real emails until it is published again."""
    service = StudioService(db, organization_id)
    return await service.restore(await service.template(template_id), version_id, user.id)


# ------------------------------------------------------------------ which template an ERPX email uses


@router.put("/assignments/{key}", response_model=MessageOut)
async def assign_template(key: str, payload: AssignRequest, organization_id: uuid.UUID = Org, user: User = Publish, db: AsyncSession = Db):
    """Use a published template for an ERPX email (for one hackathon's emails, when a hackathon is given)."""
    await StudioService(db, organization_id).assign(key, payload.template_id, payload.hackathon_id, user.id)
    return MessageOut(message="This ERPX email now uses the template.")


@router.delete("/assignments/{key}", response_model=MessageOut)
async def unassign_template(key: str, hackathon_id: uuid.UUID | None = Query(default=None), organization_id: uuid.UUID = Org, user: User = Publish, db: AsyncSession = Db):
    """Go back to the older wording (or the built-in default) for this ERPX email."""
    await StudioService(db, organization_id).unassign(key, hackathon_id)
    return MessageOut(message="This ERPX email is back to its previous wording.")


# ------------------------------------------------------------------ previews and tests


async def _check_context(request, db: AsyncSession, user: User) -> None:
    if request.context.type == "internship":
        from modules.our_internships.access import InstructorService

        if not await InstructorService(db).has_global(user, "view"):
            raise AuthorizationError("Previewing with a real student needs permission to view internships.")


@router.post("/preview", response_model=PreviewResponse)
async def preview(payload: PreviewRequest, organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    """Render the email being edited (saved or not) with sample data, or a selected student's. Nothing is sent."""
    await _check_context(payload, db, user)
    return await StudioService(db, organization_id).preview(payload.source_type, payload.draft, payload.context)


@router.post("/test", response_model=TestResponse)
async def send_test(payload: TestRequest, template_id: uuid.UUID | None = Query(default=None), organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    """Send the email being edited to one address, marked as a test, with safe sample links. It starts no ERPX workflow."""
    await _check_context(payload, db, user)
    sent, message = await StudioService(db, organization_id).send_test(payload.source_type, payload.draft, payload.context, str(payload.to_email), user.id, template_id)
    return TestResponse(sent=sent, message=message)


# ------------------------------------------------------------------ brand profiles, signatures, components, images


@router.get("/brands", response_model=list[BrandOut])
async def list_brands(organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    return await BrandingService(db, organization_id).brands()


@router.post("/brands", response_model=BrandOut, status_code=201)
async def create_brand(payload: BrandPayload, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    return await BrandingService(db, organization_id).save_brand(payload, user.id)


@router.put("/brands/{brand_id}", response_model=BrandOut)
async def update_brand(brand_id: uuid.UUID, payload: BrandPayload, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    return await BrandingService(db, organization_id).save_brand(payload, user.id, brand_id)


@router.delete("/brands/{brand_id}", response_model=MessageOut)
async def delete_brand(brand_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await BrandingService(db, organization_id).delete_brand(brand_id)
    return MessageOut(message="Deleted.")


@router.get("/signatures", response_model=list[SignatureOut])
async def list_signatures(organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    return await BrandingService(db, organization_id).signatures()


@router.post("/signatures", response_model=SignatureOut, status_code=201)
async def create_signature(payload: SignaturePayload, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    return await BrandingService(db, organization_id).save_signature(payload, user.id)


@router.put("/signatures/{signature_id}", response_model=SignatureOut)
async def update_signature(signature_id: uuid.UUID, payload: SignaturePayload, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    return await BrandingService(db, organization_id).save_signature(payload, user.id, signature_id)


@router.post("/signatures/{signature_id}/approve", response_model=SignatureOut)
async def approve_signature(signature_id: uuid.UUID, payload: ApproveSignatureRequest, organization_id: uuid.UUID = Org, user: User = Publish, db: AsyncSession = Db):
    """An uploaded signature image is only used in emails once an administrator has approved it."""
    return await BrandingService(db, organization_id).approve_signature(signature_id, payload.approve, user.id)


@router.delete("/signatures/{signature_id}", response_model=MessageOut)
async def delete_signature(signature_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await BrandingService(db, organization_id).delete_signature(signature_id)
    return MessageOut(message="Deleted.")


@router.get("/components", response_model=list[ComponentOut])
async def list_components(organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    return await BrandingService(db, organization_id).components()


@router.post("/components", response_model=ComponentOut, status_code=201)
async def create_component(payload: ComponentPayload, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    return await BrandingService(db, organization_id).save_component(payload, user.id)


@router.put("/components/{component_id}", response_model=ComponentOut)
async def update_component(component_id: uuid.UUID, payload: ComponentPayload, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    return await BrandingService(db, organization_id).save_component(payload, user.id, component_id)


@router.delete("/components/{component_id}", response_model=MessageOut)
async def delete_component(component_id: uuid.UUID, organization_id: uuid.UUID = Org, user: User = Manage, db: AsyncSession = Db):
    await BrandingService(db, organization_id).delete_component(component_id)
    return MessageOut(message="Deleted.")


@router.get("/assets", response_model=list[AssetOut])
async def list_assets(organization_id: uuid.UUID = Org, user: User = View, db: AsyncSession = Db):
    return await BrandingService(db, organization_id).assets()


@router.post("/assets", response_model=AssetOut, status_code=201)
async def upload_asset(
    purpose: str = Query(default="image", pattern="^(image|attachment)$"),
    file: UploadFile = File(...),
    organization_id: uuid.UUID = Org,
    user: User = Manage,
    db: AsyncSession = Db,
):
    """Upload an image for emails (it is served from a public link) or a PDF to attach."""
    data = await file.read(5 * 1024 * 1024 + 1)
    return await BrandingService(db, organization_id).upload(file.filename or "file", data, purpose, user.id)


# ------------------------------------------------------------------ history


@router.get("/history", response_model=list[HistoryItem])
async def history(
    status: str | None = Query(default=None),
    key: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    template_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    organization_id: uuid.UUID = Org,
    user: User = View,
    db: AsyncSession = Db,
):
    """Emails that were sent or failed: who, which template and version, when, and why one failed."""
    query = (
        select(EmailSendRecord, EmailStudioTemplate.name, EmailStudioVersion.version_number)
        .outerjoin(EmailStudioTemplate, EmailStudioTemplate.id == EmailSendRecord.template_id)
        .outerjoin(EmailStudioVersion, EmailStudioVersion.id == EmailSendRecord.version_id)
        .where(EmailSendRecord.organization_id == organization_id)
        .order_by(EmailSendRecord.created_at.desc())
        .limit(limit)
    )
    if status:
        query = query.where(EmailSendRecord.status == status)
    if key:
        query = query.where(EmailSendRecord.key == key)
    if template_id:
        query = query.where(EmailSendRecord.template_id == template_id)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(EmailSendRecord.recipient.ilike(like) | EmailSendRecord.subject.ilike(like))
    rows = (await db.execute(query)).all()
    return [
        HistoryItem(
            id=r.id, created_at=r.created_at, recipient=r.recipient, subject=r.subject, key=r.key, module=r.module, template_id=r.template_id,
            template_name=name, version_number=number, source=r.source, status=r.status, error=r.error, is_test=r.is_test, attachments=r.attachments,
        )
        for r, name, number in rows
    ]


# ------------------------------------------------------------------ public images (no sign-in: email clients fetch them)


@public_router.get("/{token}")
async def public_asset(token: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(EmailAsset).where(EmailAsset.token == token))).scalar_one_or_none()
    if row is None or not row.content_type.startswith("image/"):
        raise NotFoundError("Image", token)
    await db.refresh(row, attribute_names=["data"])
    return Response(content=row.data, media_type=row.content_type, headers=_IMAGE_HEADERS)
