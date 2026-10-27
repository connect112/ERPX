"""
Routes for the offer letter generator of an internship (``/our-internships/{id}/offer-letters``).

Reading and downloading is open to anyone who can see the internship (including its instructors). Everything that changes the
settings, the signature, the design approval, the letters or what is emailed needs ``our_internships.manage`` itself.
"""

import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceUnavailableError, ValidationError
from app.core.logging_config import get_logger
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.our_internships.access import internship_access
from modules.our_internships.letter_config import ASSET_KINDS, PLACEHOLDERS, LetterConfig
from modules.our_internships.letter_models import LetterStatus, OfferLetter
from modules.our_internships.letter_tasks import enqueue_generation, enqueue_letter_emails
from modules.our_internships.letters import LetterService
from modules.our_internships.schemas import MessageResponse
from modules.our_internships.service import OurInternshipService
from modules.users.dependencies import get_current_user_organization_id

logger = get_logger(__name__)

router = APIRouter()

_SAFE = {"X-Content-Type-Options": "nosniff"}
# an uploaded image is only ever shown inside an <img>; this stops an SVG from running anything if opened directly
_IMAGE_HEADERS = {**_SAFE, "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox"}


def _file(content: bytes, media_type: str, filename: str, disposition: str = "inline", extra: dict[str, str] | None = None) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={**(extra or _SAFE), "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}"},
    )


# ------------------------------------------------------------------ schemas


class AssetOut(BaseModel):
    kind: str
    label: str
    source: str  # internship | defaults
    filename: str
    content_type: str
    size_bytes: int
    updated_at: datetime


class SettingsOut(BaseModel):
    config: LetterConfig  # what this internship's letters are made from
    defaults: LetterConfig  # the organisation's defaults, to show what this internship overrides
    has_overrides: bool
    assets: dict[str, AssetOut | None]
    design_state: Literal["not_approved", "approved", "changed"]
    design_approved_at: datetime | None = None
    problems: list[str]
    placeholders: dict[str, str]
    internship_title: str
    counts: dict[str, int]


class SaveConfigRequest(BaseModel):
    config: LetterConfig
    scope: Literal["internship", "defaults"] = "internship"


class PreviewRequest(BaseModel):
    student_id: uuid.UUID | None = None
    config: LetterConfig | None = None  # unsaved settings; omitted means the saved ones


class LetterOut(BaseModel):
    id: uuid.UUID
    version: int
    reference: str
    status: str
    outdated: bool
    error: str | None = None
    filename: str | None = None
    page_count: int | None = None
    pdf_size: int | None = None
    generated_at: datetime | None = None
    approved_at: datetime | None = None
    delivery_status: str
    delivery_attempts: int
    delivery_error: str | None = None
    released_at: datetime | None = None
    sent_to_email: str | None = None


class StudentRow(BaseModel):
    student_id: uuid.UUID
    name: str
    email: str
    institution: str
    location: str
    issues: list[str]
    status: str  # missing_data | not_generated | pending | generating | ready | failed | approved | released
    letter: LetterOut | None = None


class StudentsResponse(BaseModel):
    students: list[StudentRow]
    counts: dict[str, int]
    in_progress: int


class GenerateRequest(BaseModel):
    student_ids: list[uuid.UUID] | None = None
    regenerate: bool = False


class BlockedStudent(BaseModel):
    student_id: uuid.UUID
    name: str
    issues: list[str]


class GenerateResponse(BaseModel):
    queued: int
    already_generated: int
    in_progress: int
    blocked: list[BlockedStudent]
    message: str


class ApproveRequest(BaseModel):
    letter_ids: list[uuid.UUID] | None = None  # empty means every letter that is ready


class ReleaseRequest(BaseModel):
    letter_ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)
    resend: bool = False


class SkippedLetter(BaseModel):
    letter_id: uuid.UUID
    name: str
    reason: str


class ReleaseResponse(BaseModel):
    queued: int
    skipped: list[SkippedLetter]
    message: str


class EmailPreviewOut(BaseModel):
    to: str
    subject: str
    body: str
    attachment: str


class TestEmailRequest(BaseModel):
    to_email: EmailStr


class DeliveryOut(BaseModel):
    id: uuid.UUID
    letter_id: uuid.UUID
    student_name: str
    recipient_email: str
    subject: str | None = None
    status: str
    attempt: int
    error: str | None = None
    created_at: datetime


class EventOut(BaseModel):
    id: uuid.UUID
    action: str
    detail: str | None = None
    letter_id: uuid.UUID | None = None
    actor_user_id: uuid.UUID | None = None
    created_at: datetime


def _letter_out(letter: OfferLetter, outdated: bool = False) -> LetterOut:
    return LetterOut(
        id=letter.id, version=letter.version, reference=letter.reference, status=letter.status, outdated=outdated, error=letter.error,
        filename=letter.filename, page_count=letter.page_count, pdf_size=letter.pdf_size, generated_at=letter.generated_at,
        approved_at=letter.approved_at, delivery_status=letter.delivery_status, delivery_attempts=letter.delivery_attempts,
        delivery_error=letter.delivery_error, released_at=letter.released_at, sent_to_email=letter.sent_to_email,
    )


async def _internship(db: AsyncSession, internship_id: uuid.UUID, organization_id: uuid.UUID):
    return await OurInternshipService(db).get(internship_id, organization_id)


# ------------------------------------------------------------------ settings and images


@router.get("/{internship_id}/offer-letters", response_model=SettingsOut)
async def get_letter_settings(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The settings the letters are made from, the images, what is still missing, and how the letters stand."""
    internship = await _internship(db, internship_id, organization_id)
    service = LetterService(db)
    loaded = await service.load(internship)
    return SettingsOut(
        config=loaded.config,
        defaults=loaded.default_config,
        has_overrides=bool(loaded.override),
        assets={k: (AssetOut(**loaded.asset_info[k]) if k in loaded.asset_info else None) for k in ASSET_KINDS},
        design_state=service.design_state(loaded),
        design_approved_at=loaded.approved_at,
        problems=service.problems(internship, loaded),
        placeholders=PLACEHOLDERS,
        internship_title=internship.title,
        counts=await service.counts(internship),
    )


@router.put("/{internship_id}/offer-letters/config", response_model=MessageResponse)
async def save_letter_config(
    internship_id: uuid.UUID,
    payload: SaveConfigRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Save the settings: for this internship only (an override of the defaults) or as the defaults for every internship."""
    internship = await _internship(db, internship_id, organization_id)
    await LetterService(db).save_config(internship, payload.config, payload.scope, user.id)
    return MessageResponse(message="Saved." if payload.scope == "internship" else "Saved as the default for every internship.")


@router.delete("/{internship_id}/offer-letters/config", response_model=MessageResponse)
async def reset_letter_config(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Drop this internship's overrides, so it follows the defaults again."""
    internship = await _internship(db, internship_id, organization_id)
    await LetterService(db).clear_override(internship, user.id)
    return MessageResponse(message="This internship now uses the defaults.")


def _kind(kind: str) -> str:
    if kind not in ASSET_KINDS:
        raise ValidationError("Unknown image type. Use: " + ", ".join(ASSET_KINDS) + ".")
    return kind


@router.put("/{internship_id}/offer-letters/assets/{kind}", response_model=MessageResponse)
async def upload_letter_asset(
    internship_id: uuid.UUID,
    kind: str,
    scope: Literal["internship", "defaults"] = Query("internship"),
    file: UploadFile = File(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Upload (or replace) the logo, watermark, signature, stamp or extra image. Only the uploaded signature is ever used."""
    internship = await _internship(db, internship_id, organization_id)
    data = await file.read(4 * 1024 * 1024 + 1)
    await LetterService(db).put_asset(internship, _kind(kind), scope, file.filename or kind, data, user.id)
    return MessageResponse(message="Uploaded.")


@router.delete("/{internship_id}/offer-letters/assets/{kind}", response_model=MessageResponse)
async def remove_letter_asset(
    internship_id: uuid.UUID,
    kind: str,
    scope: Literal["internship", "defaults"] = Query("internship"),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    await LetterService(db).remove_asset(internship, _kind(kind), scope, user.id)
    return MessageResponse(message="Removed.")


@router.get("/{internship_id}/offer-letters/assets/{kind}")
async def get_letter_asset(
    internship_id: uuid.UUID,
    kind: str,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    data, content_type = await LetterService(db).asset_bytes(internship, _kind(kind))
    return Response(content=data, media_type=content_type, headers=_IMAGE_HEADERS)


# ------------------------------------------------------------------ preview and approval


@router.post("/{internship_id}/offer-letters/preview")
async def preview_letter(
    internship_id: uuid.UUID,
    payload: PreviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The letter exactly as it would be made, for the chosen student (or a sample), from the settings on screen."""
    internship = await _internship(db, internship_id, organization_id)
    pdf, pages, sample = await LetterService(db).preview(internship, payload.student_id, payload.config)
    return _file(pdf, "application/pdf", "offer-letter-preview.pdf", extra={**_SAFE, "X-Letter-Pages": str(pages), "X-Letter-Sample": "1" if sample else "0"})


@router.post("/{internship_id}/offer-letters/approve-design", response_model=MessageResponse)
async def approve_letter_design(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Approve the saved design. Letters can only be generated from an approved design; changing anything undoes the approval."""
    internship = await _internship(db, internship_id, organization_id)
    await LetterService(db).approve_design(internship, user.id)
    return MessageResponse(message="The design is approved. You can generate the letters now.")


# ------------------------------------------------------------------ the students and their letters


@router.get("/{internship_id}/offer-letters/students", response_model=StudentsResponse)
async def letter_students(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """Every selected student with what is missing for their letter and the state of it. Poll this to follow a batch."""
    internship = await _internship(db, internship_id, organization_id)
    service = LetterService(db)
    students: list[StudentRow] = []
    counts: dict[str, int] = {"missing_data": 0, "not_generated": 0, **{s.value: 0 for s in LetterStatus}}
    for row in await service.rows(internship):
        letter: OfferLetter | None = row["letter"]
        if letter is not None:
            state = letter.status
        else:
            state = "missing_data" if row["issues"] else "not_generated"
        counts[state] += 1
        students.append(
            StudentRow(
                student_id=row["student_id"], name=row["name"], email=row["email"], institution=row["institution"], location=row["location"],
                issues=row["issues"], status=state, letter=_letter_out(letter, row["outdated"]) if letter else None,
            )
        )
    return StudentsResponse(students=students, counts=counts, in_progress=counts["pending"] + counts["generating"])


@router.post("/{internship_id}/offer-letters/generate", response_model=GenerateResponse)
async def generate_letters(
    internship_id: uuid.UUID,
    payload: GenerateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Make a PDF for each selected student (or the ones named). Students with missing details are listed, not skipped
    silently, and do not hold up the rest. Asking twice does not make duplicates. Nothing is emailed."""
    internship = await _internship(db, internship_id, organization_id)
    result = await LetterService(db).prepare(internship, user.id, payload.student_ids, payload.regenerate)
    ids: list[uuid.UUID] = result["letter_ids"]
    # queue only after the rows the worker reads are committed
    await db.commit()
    if ids:
        try:
            enqueue_generation(ids)
        except Exception as exc:  # noqa: BLE001 - e.g. the message broker is down
            logger.warning("offer_letters_enqueue_failed", internship_id=str(internship_id), exc_info=True)
            await LetterService(db).fail_unqueued(ids)
            await db.commit()
            raise ServiceUnavailableError("The letters could not be queued right now. Please press Generate again in a moment.") from exc
    parts = [f"Generating {len(ids)} letter{'s' if len(ids) != 1 else ''}." if ids else "No new letters to generate."]
    if result["already_generated"]:
        parts.append(f"{result['already_generated']} already generated.")
    if result["in_progress"]:
        parts.append(f"{result['in_progress']} already in progress.")
    if result["blocked"]:
        parts.append(f"{len(result['blocked'])} need their details fixed first.")
    return GenerateResponse(
        queued=len(ids), already_generated=result["already_generated"], in_progress=result["in_progress"],
        blocked=[BlockedStudent(**b) for b in result["blocked"]], message=" ".join(parts),
    )


@router.get("/{internship_id}/offer-letters/letters/{letter_id}/pdf")
async def download_letter(
    internship_id: uuid.UUID,
    letter_id: uuid.UUID,
    download: bool = Query(False),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    letter = await LetterService(db).letter_pdf(internship, letter_id)
    return _file(letter.pdf_data, "application/pdf", letter.filename or "OfferLetter.pdf", "attachment" if download else "inline")


@router.get("/{internship_id}/offer-letters/students/{student_id}/versions", response_model=list[LetterOut])
async def letter_versions(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """Every version of one student's letter, newest first. Versions that were sent stay available."""
    internship = await _internship(db, internship_id, organization_id)
    return [_letter_out(v) for v in await LetterService(db).versions(internship, student_id)]


@router.post("/{internship_id}/offer-letters/approve", response_model=MessageResponse)
async def approve_letters(
    internship_id: uuid.UUID,
    payload: ApproveRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Approve generated letters (the chosen ones, or every one that is ready) so they can be released."""
    internship = await _internship(db, internship_id, organization_id)
    result = await LetterService(db).approve_letters(internship, user.id, payload.letter_ids or None)
    message = f"Approved {result['approved']} letter{'s' if result['approved'] != 1 else ''}."
    if result["skipped"]:
        message += f" {result['skipped']} could not be approved (not ready, or outdated)."
    return MessageResponse(message=message)


@router.get("/{internship_id}/offer-letters/download.zip")
async def download_zip(
    internship_id: uuid.UUID,
    letter_id: list[uuid.UUID] = Query(default=[]),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The generated letters in one ZIP (the chosen ones, or all of them)."""
    internship = await _internship(db, internship_id, organization_id)
    data = await LetterService(db).zip_letters(internship, letter_id or None)
    return _file(data, "application/zip", f"OfferLetters_{internship.id.hex[:8].upper()}.zip", "attachment")


# ------------------------------------------------------------------ release


@router.post("/{internship_id}/offer-letters/email-preview", response_model=EmailPreviewOut)
async def email_preview(
    internship_id: uuid.UUID,
    payload: PreviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The email (subject, body, attachment name) one student would receive."""
    internship = await _internship(db, internship_id, organization_id)
    return EmailPreviewOut(**await LetterService(db).email_preview(internship, payload.student_id))


@router.post("/{internship_id}/offer-letters/test-email", response_model=MessageResponse)
async def send_test_email(
    internship_id: uuid.UUID,
    payload: TestEmailRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Send the real email with a sample letter to one address, to check the wording and the attachment."""
    internship = await _internship(db, internship_id, organization_id)
    await LetterService(db).send_test(internship, str(payload.to_email))
    return MessageResponse(message=f"A test email with a sample letter was sent to {payload.to_email}.")


@router.post("/{internship_id}/offer-letters/release", response_model=ReleaseResponse)
async def release_letters(
    internship_id: uuid.UUID,
    payload: ReleaseRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Email the chosen, approved letters to the students' registered addresses. This is the only thing that sends a letter."""
    internship = await _internship(db, internship_id, organization_id)
    service = LetterService(db)
    result = await service.release(internship, user.id, payload.letter_ids, payload.resend)
    ids: list[uuid.UUID] = result["queued"]
    await db.commit()
    if ids:
        try:
            enqueue_letter_emails(ids)
        except Exception as exc:  # noqa: BLE001 - e.g. the message broker is down
            logger.warning("offer_letters_email_enqueue_failed", internship_id=str(internship_id), exc_info=True)
            await service.revert_queue(ids)
            await db.commit()
            raise ServiceUnavailableError("The letters could not be queued right now. Nothing was sent; please try again.") from exc
    skipped = [SkippedLetter(**s) for s in result["skipped"]]
    message = f"Sending {len(ids)} letter{'s' if len(ids) != 1 else ''}." if ids else "Nothing was sent."
    if skipped:
        message += f" {len(skipped)} skipped."
    return ReleaseResponse(queued=len(ids), skipped=skipped, message=message)


@router.get("/{internship_id}/offer-letters/deliveries", response_model=list[DeliveryOut])
async def letter_deliveries(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """Every email attempt for this internship's letters: when, to whom, whether it went, and why not."""
    internship = await _internship(db, internship_id, organization_id)
    return [
        DeliveryOut(
            id=d.id, letter_id=d.letter_id, student_name=letter.student_name, recipient_email=d.recipient_email, subject=d.subject,
            status=d.status, attempt=d.attempt, error=d.error, created_at=d.created_at,
        )
        for d, letter in await LetterService(db).deliveries(internship)
    ]


@router.get("/{internship_id}/offer-letters/events", response_model=list[EventOut])
async def letter_events(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The audit trail: who configured, approved, generated, regenerated and released what."""
    internship = await _internship(db, internship_id, organization_id)
    return [EventOut.model_validate(e, from_attributes=True) for e in await LetterService(db).events(internship)]

