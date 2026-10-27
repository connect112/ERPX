"""Routes for internship certificates: who is eligible, preview, and bulk release."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceUnavailableError, ValidationError
from app.core.logging_config import get_logger
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.internship_learning.certificate_schemas import (
    CertificateInfo,
    CertificatesOverview,
    EligibilityRequest,
    EligibilityRow,
    IssueRequest,
    IssueResponse,
    PlanOut,
    Recipient,
)
from modules.internship_learning.certificates import KINDS, LABELS, CertificateService
from modules.our_internships.service import OurInternshipService
from modules.users.dependencies import get_current_user_organization_id
from modules.workshop_exams.tasks import enqueue_certificates

logger = get_logger(__name__)

router = APIRouter()


async def _overview(service: CertificateService, internship, exams) -> CertificatesOverview:
    rows = await service.rows(internship, exams)
    sent = await service.exams.sent_counts([e.id for e in exams.values()])
    return CertificatesOverview(
        certificates=[
            CertificateInfo(
                kind=kind,
                label=LABELS[kind],
                exam_id=exams[kind].id,
                has_design=exams[kind].has_certificate_template,
                review_required=exams[kind].certificate_review,
                eligible_count=sum(1 for r in rows if r["kind"] == kind),
                sent_count=sent.get(exams[kind].id, 0),
            )
            for kind in KINDS
            if kind in exams
        ],
        rows=[EligibilityRow(**r) for r in rows],
    )


@router.post("/{internship_id}/certificates/open", response_model=CertificatesOverview)
async def open_certificates(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """The two certificates (participation and completion) and who is eligible for each. They are created the first time
    this is opened, each a full certificate set-up (design, ID format, review, preview and test emails)."""
    internship = await OurInternshipService(db).get(internship_id, organization_id)
    service = CertificateService(db)
    exams = await service.ensure_exams(internship)
    result = await _overview(service, internship, exams)
    await db.commit()
    return result


@router.get("/{internship_id}/certificates", response_model=CertificatesOverview)
async def certificates_overview(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    internship = await OurInternshipService(db).get(internship_id, organization_id)
    service = CertificateService(db)
    return await _overview(service, internship, await service.existing_exams(internship_id))


@router.put("/{internship_id}/certificates/eligibility", response_model=CertificatesOverview)
async def set_eligibility(
    internship_id: uuid.UUID,
    payload: EligibilityRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Choose the certificate these students are eligible for (or none). A student is on one list only."""
    internship = await OurInternshipService(db).get(internship_id, organization_id)
    service = CertificateService(db)
    await service.set_kind(internship, payload.selection_ids, payload.kind, user.id)
    return await _overview(service, internship, await service.existing_exams(internship_id))


@router.post("/{internship_id}/certificates/issue", response_model=IssueResponse)
async def issue_certificates(
    internship_id: uuid.UUID,
    payload: IssueRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Release the certificates. Without `confirm` it only lists who would get what. With it, the certificates are
    created and emailed, or held for review where review is switched on for that certificate."""
    bad = [k for k in payload.kinds if k not in KINDS]
    if bad:
        raise ValidationError("Choose participation, completion or both.")
    internship = await OurInternshipService(db).get(internship_id, organization_id)
    service = CertificateService(db)
    exams = await service.ensure_exams(internship)
    people = await service.people(internship)

    plans, out = {}, []
    for kind in KINDS:
        if kind not in payload.kinds:
            continue
        plan = await service.plan(internship, exams[kind], people[kind])
        plans[kind] = plan
        out.append(
            PlanOut(
                kind=kind,
                label=LABELS[kind],
                exam_id=exams[kind].id,
                recipients=[Recipient(name=r.name, email=r.email, status=r.status) for r in plan.recipients],
                will_send=plan.will_send,
                already_sent=plan.count("already_sent"),
                no_email=plan.count("no_email"),
                review_required=exams[kind].certificate_review,
            )
        )
    if not payload.confirm:
        await db.commit()
        return IssueResponse(plans=out)

    to_send: list[uuid.UUID] = []
    held: list[str] = []
    for kind, plan in plans.items():
        if plan.will_send == 0:
            continue
        ids = await service.issue(exams[kind], plan)
        if exams[kind].certificate_review:
            held.append(LABELS[kind])
        else:
            to_send.extend(ids)
    await db.commit()
    if to_send:
        try:
            enqueue_certificates(to_send)
        except Exception:  # noqa: BLE001 - e.g. the message broker is down
            logger.warning("internship_certificates_enqueue_failed", internship_id=str(internship_id), exc_info=True)
            raise ServiceUnavailableError("The certificates are ready but couldn't be queued just now. Press Send again to retry.") from None
    parts = []
    if to_send:
        parts.append(f"Queued {len(to_send)} certificate email(s).")
    if held:
        parts.append(f"Added for review (not emailed yet): {', '.join(held)}. Open Review certificates to check and send them.")
    return IssueResponse(plans=out, done=True, held_for_review=held, message=" ".join(parts) or "Nobody needs a certificate right now.")
