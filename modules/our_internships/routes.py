"""
Admin routes for Our Internships (our_internships.view / our_internships.manage): create an internship, look at how the
students of its institution or event performed, and keep the shortlist of selected students.
"""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError, ValidationError
from app.core.logging_config import get_logger
from app.db.session import get_db
from modules.authentication.models import User
from modules.our_internships.access import InstructorService, internship_access
from modules.our_internships.models import OurInternship
from modules.our_internships.schemas import (
    BulkOnboardingRequest,
    BulkOnboardingResponse,
    CourseOption,
    GrantLmsRequest,
    GrantLmsResponse,
    GrantResult,
    InternshipCreateRequest,
    InternshipOut,
    InternshipUpdateRequest,
    MessageResponse,
    OfferEmailRequest,
    OfferPreviewRequest,
    OfferReleaseRequest,
    OfferReleaseResponse,
    OfferSettings,
    OfferTestEmailRequest,
    OnboardingUpdateRequest,
    PerformanceResponse,
    SelectedListResponse,
    SelectedStudent,
    SelectionNoteRequest,
    SelectRequest,
)
from modules.our_internships.offer_letter import OfferLayout
from modules.our_internships.offers import OfferService
from modules.our_internships.onboarding import MAX_BULK_GRANT, OnboardingService, notify_access
from modules.our_internships.service import OurInternshipService
from modules.our_internships.tasks import enqueue_offers
from modules.users.dependencies import get_current_user_organization_id

logger = get_logger(__name__)

router = APIRouter()

_PDF_HEADERS = {"X-Content-Type-Options": "nosniff"}


async def _out(service: OurInternshipService, internships: list[OurInternship]) -> list[InternshipOut]:
    institutions, events, counts, courses = await service.names(internships)
    out = []
    for i in internships:
        item = InternshipOut.model_validate(i)
        item.institution_name = institutions.get(i.institution_id)
        item.event_name = events.get(i.event_id)
        item.selected_count = counts.get(i.id, 0)
        item.lms_course_title = courses.get(i.lms_course_id)
        out.append(item)
    return out


@router.get("", response_model=list[InternshipOut])
async def list_internships(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    internships = await service.list_all(organization_id)
    allowed = await InstructorService(db).restricted_ids(user)  # None: may see all; else only the ones they instruct now
    if allowed is not None:
        internships = [i for i in internships if i.id in allowed]
    return await _out(service, internships)


@router.post("", response_model=InternshipOut, status_code=status.HTTP_201_CREATED)
async def create_internship(
    payload: InternshipCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    internship = await service.create(organization_id, user.id, **payload.model_dump())
    return (await _out(service, [internship]))[0]


@router.get("/{internship_id}", response_model=InternshipOut)
async def get_internship(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    return (await _out(service, [await service.get(internship_id, organization_id)]))[0]


@router.patch("/{internship_id}", response_model=InternshipOut)
async def update_internship(
    internship_id: uuid.UUID,
    payload: InternshipUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    internship = await service.update(await service.get(internship_id, organization_id), payload.model_dump(exclude_unset=True))
    return (await _out(service, [internship]))[0]


@router.delete("/{internship_id}", response_model=MessageResponse)
async def delete_internship(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    await service.delete(await service.get(internship_id, organization_id))
    return MessageResponse(message="Internship deleted.")


@router.get("/{internship_id}/performance", response_model=PerformanceResponse)
async def performance(
    internship_id: uuid.UUID,
    institution_id: uuid.UUID | None = Query(default=None, description="Narrow an all-students internship to one institution."),
    event_id: uuid.UUID | None = Query(default=None, description="Narrow to one event."),
    q: str | None = Query(default=None, max_length=100),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The students (and, grouped by hackathon team, the teams) this internship can select from, with their workshop exam
    marks, hackathon team score and individual score. Read live from the events' exams and hackathons."""
    service = OurInternshipService(db)
    internship = await service.get(internship_id, organization_id)
    return await service.performance(internship, institution_id, event_id, q)


@router.get("/{internship_id}/selected", response_model=SelectedListResponse)
async def selected_students(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    items = await service.selected(await service.get(internship_id, organization_id))
    return SelectedListResponse(items=items, total=len(items))


@router.post("/{internship_id}/selected", response_model=MessageResponse)
async def select_students(
    internship_id: uuid.UUID,
    payload: SelectRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    internship = await service.get(internship_id, organization_id)
    added, already = await service.select(internship, payload.student_ids, user.id, payload.note)
    return MessageResponse(message=f"{added} added to the selected list" + (f", {already} already on it." if already else "."))


@router.patch("/{internship_id}/selected/{student_id}", response_model=MessageResponse)
async def update_selection_note(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: SelectionNoteRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    await service.set_note(await service.get(internship_id, organization_id), student_id, payload.note)
    return MessageResponse(message="Saved.")


@router.delete("/{internship_id}/selected/{student_id}", response_model=MessageResponse)
async def unselect_student(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OurInternshipService(db)
    await service.unselect(await service.get(internship_id, organization_id), student_id)
    return MessageResponse(message="Removed from the selected list.")

# ================================================================ offer letters


def _pdf(content: bytes, filename: str, disposition: str = "inline") -> Response:
    return Response(
        content=content,
        media_type="application/pdf",
        headers={**_PDF_HEADERS, "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/{internship_id}/offer", response_model=OfferSettings)
async def get_offer_settings(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The offer letter template, where details go on it, the email and what is left to do before releasing."""
    service = OfferService(db)
    return await service.settings(await service.get(internship_id, organization_id))


@router.put("/{internship_id}/offer/template", response_model=OfferSettings)
async def upload_offer_template(
    internship_id: uuid.UUID,
    file: UploadFile = File(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OfferService(db)
    internship = await service.get(internship_id, organization_id)
    await service.set_template(internship, file.filename or "offer-letter.pdf", await file.read())
    return await service.settings(internship)


@router.delete("/{internship_id}/offer/template", response_model=OfferSettings)
async def remove_offer_template(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OfferService(db)
    internship = await service.get(internship_id, organization_id)
    await service.remove_template(internship)
    return await service.settings(internship)


@router.get("/{internship_id}/offer/template")
async def download_offer_template(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The uploaded PDF itself, for showing the page while placing the fields."""
    internship = await OfferService(db).get(internship_id, organization_id)
    if not internship.offer_template_data:
        raise NotFoundError("Offer letter template")
    return _pdf(internship.offer_template_data, internship.offer_template_filename or "offer-letter.pdf")


@router.put("/{internship_id}/offer/layout", response_model=OfferSettings)
async def save_offer_layout(
    internship_id: uuid.UUID,
    payload: OfferLayout,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = OfferService(db)
    internship = await service.get(internship_id, organization_id)
    await service.set_layout(internship, payload)
    return await service.settings(internship)


@router.put("/{internship_id}/offer/email", response_model=OfferSettings)
async def save_offer_email(
    internship_id: uuid.UUID,
    payload: OfferEmailRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """The email that carries each letter. Empty subject and body mean the standard wording."""
    service = OfferService(db)
    internship = await service.get(internship_id, organization_id)
    await service.set_email(internship, payload.subject, payload.body, payload.offer_date)
    return await service.settings(internship)


@router.post("/{internship_id}/offer/preview")
async def preview_offer_letter(
    internship_id: uuid.UUID,
    payload: OfferPreviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """A sample letter. Pass ``layout`` to preview field positions that are not saved yet."""
    service = OfferService(db)
    internship = await service.get(internship_id, organization_id)
    return _pdf(service.sample_letter(internship, payload.layout), "offer-letter-preview.pdf")


@router.get("/{internship_id}/selected/{student_id}/offer.pdf")
async def student_offer_letter(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """One student's letter exactly as it will be (or was) sent, for checking before release."""
    service = OfferService(db)
    pdf, filename = await service.student_letter(await service.get(internship_id, organization_id), student_id)
    return _pdf(pdf, filename)


@router.post("/{internship_id}/offer/test-email", response_model=MessageResponse)
async def send_test_offer_email(
    internship_id: uuid.UUID,
    payload: OfferTestEmailRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Send the real email with a sample letter to one address (yours), so the wording and the letter can be checked."""
    service = OfferService(db)
    await service.send_test(await service.get(internship_id, organization_id), str(payload.to_email))
    return MessageResponse(message=f"A test email with a sample letter was sent to {payload.to_email}.")


@router.post("/{internship_id}/offers/release", response_model=OfferReleaseResponse)
async def release_offers(
    internship_id: uuid.UUID,
    payload: OfferReleaseRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Generate each selected student's letter from the template and email it to their registered address. The sends run
    in the background; each student's status (queued, sent, failed with the reason) shows on the selected list."""
    service = OfferService(db)
    internship = await service.get(internship_id, organization_id)
    ids, already_sent = await service.release(internship, payload.student_ids, payload.resend)
    # queue only after the rows the workers read are committed
    await db.commit()
    if ids:
        try:
            enqueue_offers(ids)
        except Exception as exc:  # noqa: BLE001 - e.g. the message broker is down
            logger.warning("internship_offers_enqueue_failed", internship_id=str(internship_id), exc_info=True)
            await service.revert_queue(ids)
            await db.commit()
            raise ServiceUnavailableError("The offers could not be queued right now. Nothing was sent; please try again.") from exc
    if not ids:
        message = "Nobody needs an offer right now." + (f" {already_sent} already sent." if already_sent else "")
    else:
        message = f"Sending {len(ids)} offer letter{'s' if len(ids) != 1 else ''}." + (
            f" {already_sent} were already sent." if already_sent else ""
        )
    return OfferReleaseResponse(queued=len(ids), already_sent=already_sent, message=message)

# ================================================================ onboarding: verification, payment, LMS access


async def _one(service: OurInternshipService, internship: OurInternship, student_id: uuid.UUID) -> SelectedStudent:
    items = await service.selected(internship, only_student_id=student_id)
    if not items:
        raise NotFoundError("Selected student", student_id)
    return items[0]


@router.get("/{internship_id}/selected/{student_id}", response_model=SelectedStudent)
async def selected_student(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """One selected student's profile: results, offer, verification, payment and LMS access."""
    service = OurInternshipService(db)
    return await _one(service, await service.get(internship_id, organization_id), student_id)


@router.get("/{internship_id}/lms/courses", response_model=list[CourseOption])
async def lms_courses(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """The courses a student can be enrolled in when given LMS access."""
    await OurInternshipService(db).get(internship_id, organization_id)
    return [CourseOption(id=c.id, title=c.title, is_published=c.is_published) for c in await OnboardingService(db).courses(organization_id)]


@router.patch("/{internship_id}/selected/{student_id}/onboarding", response_model=SelectedStudent)
async def update_onboarding(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: OnboardingUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Record the student's answer to the offer, the result of verification, or that payment was received."""
    from modules.internship_onboarding.service import guard_manual_override

    service = OurInternshipService(db)
    internship = await service.get(internship_id, organization_id)
    fields = payload.model_dump(exclude_unset=True)
    await guard_manual_override(db, internship, user, fields)
    await OnboardingService(db).update_one(internship, student_id, user.id, fields)
    return await _one(service, internship, student_id)


@router.post("/{internship_id}/onboarding/bulk", response_model=BulkOnboardingResponse)
async def update_onboarding_bulk(
    internship_id: uuid.UUID,
    payload: BulkOnboardingRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Mark several students at once (all verified, all paid...). A student who cannot take the change is reported by name."""
    service = OurInternshipService(db)
    internship = await service.get(internship_id, organization_id)
    fields = payload.model_dump(exclude_unset=True, exclude={"student_ids"})
    fields = {k: v for k, v in fields.items() if v is not None}
    from modules.internship_onboarding.service import guard_manual_override

    await guard_manual_override(db, internship, user, fields)
    changed, problems = await OnboardingService(db).update_many(internship, payload.student_ids, user.id, fields)
    return BulkOnboardingResponse(changed=changed, problems=problems)


@router.post("/{internship_id}/selected/{student_id}/lms/grant", response_model=SelectedStudent)
async def grant_lms_access(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Give the student access to the LMS: an account (or their existing one) enrolled in the internship's course, and an
    email telling them how to sign in. Only once verification and payment are both confirmed."""
    service = OurInternshipService(db)
    internship = await service.get(internship_id, organization_id)
    onboarding = OnboardingService(db)
    selection, student = await onboarding.selection(internship, student_id)
    outcome = await onboarding.grant(internship, selection, student, user.id)
    result = await _one(service, internship, student_id)
    # tell the student only once the access is saved
    await db.commit()
    await notify_access(outcome)
    return result


@router.post("/{internship_id}/lms/grant", response_model=GrantLmsResponse)
async def grant_lms_access_bulk(
    internship_id: uuid.UUID,
    payload: GrantLmsRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Give LMS access to several students (up to 25 at a time, each account takes a moment to create). One that cannot be
    granted (not verified yet, an account that is not a student's) is reported and does not stop the others."""
    if len(payload.student_ids) > MAX_BULK_GRANT:
        raise ValidationError(f"Grant access to at most {MAX_BULK_GRANT} students at a time.")
    service = OurInternshipService(db)
    internship = await service.get(internship_id, organization_id)
    onboarding = OnboardingService(db)
    results, outcomes = [], []
    for selection, student in await onboarding.selections(internship, payload.student_ids):
        try:
            async with db.begin_nested():
                outcome = await onboarding.grant(internship, selection, student, user.id)
            outcomes.append(outcome)
            results.append(GrantResult(student_id=student.id, name=student.name, ok=True, message="LMS access granted."))
        except (ValidationError, ConflictError) as exc:
            results.append(GrantResult(student_id=student.id, name=student.name, ok=False, message=str(exc.message)))
    await db.commit()
    for outcome in outcomes:
        await notify_access(outcome)
    return GrantLmsResponse(granted=len(outcomes), results=results)


@router.post("/{internship_id}/selected/{student_id}/lms/revoke", response_model=SelectedStudent)
async def revoke_lms_access(
    internship_id: uuid.UUID,
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Withdraw access to the course (the account itself stays). It can be granted again."""
    service = OurInternshipService(db)
    internship = await service.get(internship_id, organization_id)
    onboarding = OnboardingService(db)
    selection, _ = await onboarding.selection(internship, student_id)
    await onboarding.revoke(internship, selection)
    return await _one(service, internship, student_id)


from modules.our_internships import student_routes  # noqa: E402

router.include_router(student_routes.router)


from modules.our_internships import instructor_routes  # noqa: E402

router.include_router(instructor_routes.router)

from modules.our_internships import letter_routes  # noqa: E402

router.include_router(letter_routes.router)
