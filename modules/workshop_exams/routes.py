"""
Admin-facing routes for workshop exams (workshops.manage / workshops.view
permissions, same as the Workshops module they belong with), plus the
unauthenticated attendee flow in the second router below -- an attendee's
unguessable emailed token is their only credential, so those routes
deliberately carry no user dependency at all.
"""

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceUnavailableError, ValidationError
from app.core.limiter import limiter
from app.core.logging_config import get_logger
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id
from modules.workshop_exams.certificate_template import (
    MAX_UPLOAD_BYTES,
    TemplateError,
    normalize_template,
    sample_certificate_pdf,
)
from modules.workshop_exams.schemas import (
    AnswersRequest,
    AttendeeAdmin,
    AttendeeUpdateRequest,
    AttendeesImportRequest,
    AttendeesImportResponse,
    CertificatePreviewRequest,
    CertificateTestEmailRequest,
    CertificateVerification,
    DashboardResponse,
    ExamCreateRequest,
    ExamPublicAdmin,
    ExamStatusRequest,
    ExamUpdateRequest,
    InvitesRequest,
    InvitesResponse,
    CertificateRecipient,
    HackathonCertificatesRequest,
    HackathonCertificatesResponse,
    MessageResponse,
    PublicExamInfo,
    PublicJoinInfo,
    PublicStartResponse,
    PublicSubmitResponse,
    QuestionAdmin,
    QuestionInput,
    QuestionsAddRequest,
    RegisterRequest,
    RegisterResponse,
    SendCertificatesRequest,
)
from modules.workshop_exams.hackathon_certificates import HackathonCertificates
from modules.workshop_exams.service import WorkshopExamService
from modules.workshop_exams.tasks import enqueue_certificates, enqueue_invite_best_effort, enqueue_invites

from packages.email.service import EmailAttachment, email_service
from modules.email_templates.render import render_email

logger = get_logger(__name__)

router = APIRouter()
public_router = APIRouter()


def _exam_out(exam, question_count: int, attendee_count: int) -> ExamPublicAdmin:
    out = ExamPublicAdmin.model_validate(exam)
    out.question_count = question_count
    out.attendee_count = attendee_count
    return out


# ---------------- admin ----------------


@router.post("", response_model=ExamPublicAdmin, status_code=status.HTTP_201_CREATED)
async def create_exam(
    payload: ExamCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    exam = await WorkshopExamService(db).create_exam(organization_id, **payload.model_dump())
    return _exam_out(exam, 0, 0)


@router.get("", response_model=list[ExamPublicAdmin])
async def list_exams(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.view")),
    db: AsyncSession = Depends(get_db),
):
    rows = await WorkshopExamService(db).list_exams(organization_id)
    return [_exam_out(exam, q, a) for exam, q, a in rows]


@router.get("/{exam_id}", response_model=ExamPublicAdmin)
async def get_exam(
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.view")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    q, a = await service.counts_for(exam.id)
    return _exam_out(exam, q, a)


@router.patch("/{exam_id}", response_model=ExamPublicAdmin)
async def update_exam(
    exam_id: uuid.UUID,
    payload: ExamUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    # exclude_unset: an omitted key means "leave it", an explicit null on
    # certificate_release_at means "unschedule".
    fields = payload.model_dump(exclude_unset=True)
    if "certificate_release_at" in fields and exam.certificates_dispatched_at is not None:
        fields.pop("certificate_release_at")
    exam = await service.update_exam(exam, fields)
    q, a = await service.counts_for(exam.id)
    return _exam_out(exam, q, a)


@router.put("/{exam_id}/certificate/template", response_model=ExamPublicAdmin)
async def upload_certificate_template(
    exam_id: uuid.UUID,
    file: UploadFile = File(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        jpeg, width_px, height_px = normalize_template(raw)
    except TemplateError as exc:
        raise ValidationError(str(exc)) from exc
    exam = await service.set_template(exam, jpeg, width_px, height_px)
    q, a = await service.counts_for(exam.id)
    return _exam_out(exam, q, a)


@router.delete("/{exam_id}/certificate/template", response_model=ExamPublicAdmin)
async def remove_certificate_template(
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.clear_template(await service.get_exam(exam_id, organization_id))
    q, a = await service.counts_for(exam.id)
    return _exam_out(exam, q, a)


@router.get("/{exam_id}/certificate/template")
async def get_certificate_template(
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.view")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    template = await service.get_template(exam.id)
    if template is None:
        raise ValidationError("No certificate design has been uploaded yet.")
    return Response(
        content=template.data,
        media_type=template.content_type,
        headers={"Cache-Control": "private, no-store"},
    )


async def _sample_pdf(service: WorkshopExamService, exam, payload: CertificatePreviewRequest) -> bytes:
    template = await service.get_template(exam.id)
    if template is None:
        raise ValidationError("Upload the certificate design first.")
    return sample_certificate_pdf(
        template.data, template.width_px, template.height_px, service.layout_of(exam, payload.layout)
    )


@router.post("/{exam_id}/certificate/preview")
async def preview_certificate(
    exam_id: uuid.UUID,
    payload: CertificatePreviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.view")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    pdf = await _sample_pdf(service, exam, payload)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="certificate-preview.pdf"', "Cache-Control": "no-store"},
    )


@router.post("/{exam_id}/certificate/test-email", response_model=MessageResponse)
async def email_test_certificate(
    exam_id: uuid.UUID,
    payload: CertificateTestEmailRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Mail a sample certificate (placeholder name) so the admin can see the
    real email, attachment and SMTP delivery before the live send."""
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    pdf = await _sample_pdf(service, exam, payload)
    subject, text, html = await render_email(
        db,
        "workshop_certificate",
        {"full_name": "Sample Student Name", "exam_title": exam.title},
        organization_id=organization_id,
    )
    sent = await email_service.send(
        str(payload.email),
        f"[TEST] {subject}",
        text,
        html,
        attachments=[EmailAttachment(filename="Certificate_sample.pdf", content=pdf, mime_type="application/pdf")],
    )
    if not sent:
        raise ValidationError("The email could not be sent. Check the email (SMTP) settings.")
    return MessageResponse(message=f"A sample certificate was sent to {payload.email}.")


@router.delete("/{exam_id}", response_model=MessageResponse)
async def delete_exam(
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    await service.delete_exam(await service.get_exam(exam_id, organization_id))
    return MessageResponse(message="Workshop exam deleted.")


@router.post("/{exam_id}/status", response_model=ExamPublicAdmin)
async def set_exam_status(
    exam_id: uuid.UUID,
    payload: ExamStatusRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.set_status(await service.get_exam(exam_id, organization_id), payload.status)
    q, a = await service.counts_for(exam.id)
    return _exam_out(exam, q, a)


@router.post("/{exam_id}/questions", response_model=list[QuestionAdmin], status_code=status.HTTP_201_CREATED)
async def add_questions(
    exam_id: uuid.UUID,
    payload: QuestionsAddRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    created = await service.add_questions(exam, [q.model_dump() for q in payload.questions])
    return [QuestionAdmin.model_validate(q) for q in created]


@router.get("/{exam_id}/questions", response_model=list[QuestionAdmin])
async def list_questions(
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.view")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    return [QuestionAdmin.model_validate(q) for q in await service.list_questions(exam.id)]


@router.put("/{exam_id}/questions/{question_id}", response_model=QuestionAdmin)
async def update_question(
    exam_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: QuestionInput,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    question = await service.update_question(exam, question_id, payload.model_dump())
    return QuestionAdmin.model_validate(question)


@router.delete("/{exam_id}/questions/{question_id}", response_model=MessageResponse)
async def delete_question(
    exam_id: uuid.UUID,
    question_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    await service.delete_question(await service.get_exam(exam_id, organization_id), question_id)
    return MessageResponse(message="Question deleted.")


@router.post("/{exam_id}/attendees", response_model=AttendeesImportResponse)
async def import_attendees(
    exam_id: uuid.UUID,
    payload: AttendeesImportRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    added, skipped = await service.import_attendees(exam, [(a.name, str(a.email)) for a in payload.attendees])
    return AttendeesImportResponse(added=added, skipped_duplicates=skipped)


@router.get("/{exam_id}/attendees", response_model=list[AttendeeAdmin])
async def list_attendees(
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.view")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    return [AttendeeAdmin.model_validate(a) for a in await service.list_attendees(exam.id)]


@router.patch("/{exam_id}/attendees/{attendee_id}", response_model=AttendeeAdmin)
async def update_attendee(
    exam_id: uuid.UUID,
    attendee_id: uuid.UUID,
    payload: AttendeeUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Correct an attendee's name or email. Their personal exam link stays the same."""
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    attendee, send_link = await service.update_attendee(
        exam, attendee_id, payload.name, str(payload.email) if payload.email else None, payload.send_link
    )
    result = AttendeeAdmin.model_validate(attendee)
    await db.commit()
    if send_link:
        enqueue_invite_best_effort(attendee.id)
    return result


@router.post("/{exam_id}/attendees/{attendee_id}/reset-submission", response_model=MessageResponse)
async def reset_attendee_submission(
    exam_id: uuid.UUID,
    attendee_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Delete one person's submission (answers, score and timer) so they can sit the exam again."""
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    attendee = await service.reset_submission(exam, attendee_id)
    return MessageResponse(message=f"{attendee.name}'s submission was deleted. They can sit the exam again with their link.")


@router.delete("/{exam_id}/attendees/{attendee_id}", response_model=MessageResponse)
async def delete_attendee(
    exam_id: uuid.UUID,
    attendee_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Remove an attendee, their submission and any certificate issued to them."""
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    await service.delete_attendee(exam, attendee_id)
    return MessageResponse(message="The attendee was removed.")


@router.post("/{exam_id}/invites", response_model=InvitesResponse)
async def send_invites(
    exam_id: uuid.UUID,
    payload: InvitesRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    ids = await service.mark_invites(exam, payload.resend_all)
    # The session commits when the request finishes; queue after flush so a
    # worker can't pick a task up before the rows it reads are visible.
    await db.commit()
    enqueue_invites(ids)
    return InvitesResponse(queued=len(ids))


@router.get("/{exam_id}/dashboard", response_model=DashboardResponse)
async def dashboard(
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.view")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    data = await service.dashboard(exam)
    data["attendees"] = [AttendeeAdmin.model_validate(a) for a in data["attendees"]]
    return DashboardResponse(**data)


@router.get("/{exam_id}/results.csv")
async def export_results(
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.view")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    out = io.StringIO()
    writer = csv.writer(out)
    info_fields = exam.info_fields or []
    writer.writerow(
        ["Name", "Email"]
        + [_csv_safe(f["label"]) for f in info_fields]
        + ["Started", "Submitted", "Score", "Total", "Certificate No", "Certificate sent"]
    )
    for a in await service.list_attendees(exam.id):
        if a.certificate_only:
            continue  # given a certificate only; they did not sit the exam
        writer.writerow(
            [
                _csv_safe(a.name),
                a.email,
                *[_csv_safe((a.info or {}).get(f["key"], "")) for f in info_fields],
                a.started_at.isoformat() if a.started_at else "",
                a.submitted_at.isoformat() if a.submitted_at else "",
                a.score if a.score is not None else "",
                a.total_marks if a.total_marks is not None else "",
                a.certificate_number or "",
                a.certificate_sent_at.isoformat() if a.certificate_sent_at else "",
            ]
        )
    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="exam-results-{exam.id}.csv"'},
    )


def _csv_safe(value: str) -> str:
    # Uploaded names can start with = + - @, which spreadsheet apps treat
    # as a formula when the exported CSV is opened.
    return f"'{value}" if value and value[0] in "=+-@" else value


@router.post("/{exam_id}/certificates/send-now", response_model=MessageResponse)
async def send_certificates_now(
    exam_id: uuid.UUID,
    payload: SendCertificatesRequest | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    ids = await service.dispatch_certificates(
        exam, include_in_progress=bool(payload and payload.include_in_progress)
    )
    await db.commit()
    try:
        enqueue_certificates(ids)
    except Exception as exc:  # noqa: BLE001 - e.g. the message broker is down
        # Un-mark the exam so pressing Send again (or the scheduler) retries;
        # otherwise these certificates would never go out.
        exam.certificates_dispatched_at = None
        await db.commit()
        logger.warning("workshop_certificates_enqueue_failed", exam_id=str(exam_id), exc_info=True)
        raise ServiceUnavailableError("Couldn't queue the certificate emails just now. Please try again.") from exc
    return MessageResponse(message=f"Queued {len(ids)} certificate email(s). The exam is now closed.")


@router.post("/{exam_id}/certificates/hackathon", response_model=HackathonCertificatesResponse)
async def send_hackathon_certificates(
    exam_id: uuid.UUID,
    payload: HackathonCertificatesRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage", "hackathons.view")),
    db: AsyncSession = Depends(get_db),
):
    """Give the people of a hackathon this exam's certificate (same design and wording), emailed with their
    own name on it. Without `confirm` it only lists who would receive one; with it, they are added and sent.
    Nobody is invited to, or scored in, the exam itself."""
    service = WorkshopExamService(db)
    exam = await service.get_exam(exam_id, organization_id)
    helper = HackathonCertificates(db)
    plan = await helper.plan(exam, organization_id, payload.hackathon_id, payload.audience, payload.top_n)
    response = HackathonCertificatesResponse(
        hackathon_title=plan.hackathon_title,
        recipients=[
            CertificateRecipient(name=r.name, email=r.email, team_name=r.team_name, status=r.status)
            for r in plan.recipients
        ],
        will_send=plan.will_send,
        already_sent=plan.count("already_sent"),
        on_exam=plan.count("on_exam"),
        no_email=plan.count("no_email"),
    )
    if not payload.confirm:
        return response
    if plan.will_send == 0:
        response.message = "Nobody needs a certificate right now."
        return response
    ids = await helper.issue(exam, plan)
    await db.commit()
    try:
        enqueue_certificates(ids)
    except Exception:  # noqa: BLE001 - e.g. the message broker is down
        # The people are saved with their certificate numbers; pressing the button again sends the unsent ones.
        logger.warning("hackathon_certificates_enqueue_failed", exam_id=str(exam_id), exc_info=True)
        raise ServiceUnavailableError(
            "The certificates are ready but couldn't be queued just now. Press Send again to retry."
        ) from None
    response.sent = True
    response.message = f"Queued {len(ids)} certificate email(s) for {plan.hackathon_title}."
    return response


# ---------------- public: attendee flow (token = credential) ----------------
#
# Exempt from the per-IP rate limiter on purpose: a whole workshop room
# sits behind one venue IP, so 200 people autosaving every few seconds
# would otherwise trip it. The 192-bit token is what gates access.


@public_router.get("/workshop-exams/join/{code}", response_model=PublicJoinInfo)
@limiter.exempt
async def public_join_info(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    service = WorkshopExamService(db)
    return PublicJoinInfo(**await service.join_info(await service.get_by_public_code(code)))


@public_router.post("/workshop-exams/join/{code}/register", response_model=RegisterResponse)
@limiter.exempt
async def public_register(
    code: str,
    payload: RegisterRequest,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopExamService(db)
    exam = await service.get_by_public_code(code)
    attendee = await service.register(exam, payload.name, str(payload.email), payload.info)
    if attendee is None:
        # Already registered: don't hand the personal link to whoever typed
        # the address -- email it to the address itself instead.
        existing_id = await service.resend_existing_link(exam, str(payload.email))
        await db.commit()
        if existing_id:
            background.add_task(enqueue_invite_best_effort, existing_id)
        return RegisterResponse(already_registered=True)
    attendee.invited_at = datetime.now(timezone.utc)
    await db.commit()
    # Backup copy of their personal link, in case they close this tab. Queued
    # after the response so a slow broker can never keep a student waiting.
    background.add_task(enqueue_invite_best_effort, attendee.id)
    return RegisterResponse(token=attendee.access_token)


@public_router.get("/workshop-exams/{token}", response_model=PublicExamInfo)
@limiter.exempt
async def public_exam_info(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    service = WorkshopExamService(db)
    attendee, exam = await service.get_by_token(token)
    return PublicExamInfo(**await service.public_info(attendee, exam))


@public_router.post("/workshop-exams/{token}/start", response_model=PublicStartResponse)
@limiter.exempt
async def public_start_exam(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    service = WorkshopExamService(db)
    attendee, exam = await service.get_by_token(token)
    return PublicStartResponse(**await service.start(attendee, exam))


@public_router.put("/workshop-exams/{token}/answers", response_model=MessageResponse)
@limiter.exempt
async def public_save_answers(
    token: str, payload: AnswersRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    service = WorkshopExamService(db)
    attendee, exam = await service.get_by_token(token)
    await service.save_answers(attendee, exam, payload.answers)
    return MessageResponse(message="Saved.")


@public_router.post("/workshop-exams/{token}/submit", response_model=PublicSubmitResponse)
@limiter.exempt
async def public_submit_exam(
    token: str, payload: AnswersRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    service = WorkshopExamService(db)
    attendee, exam = await service.get_by_token(token)
    return PublicSubmitResponse(**await service.submit(attendee, exam, payload.answers))


@public_router.get("/workshop-certificates/verify/{certificate_number}", response_model=CertificateVerification)
@limiter.limit("30/minute")
async def verify_workshop_certificate(
    certificate_number: str, request: Request, db: AsyncSession = Depends(get_db)
):
    return CertificateVerification(**await WorkshopExamService(db).verify_certificate(certificate_number))
