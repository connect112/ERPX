"""
Removing a selected student must never silently erase anything that happened to them. Removal deletes the selection row, which cascades to
(or detaches) everything keyed on it, so it is allowed only for a selection that is genuinely untouched: no sent offer, offer response,
verification, onboarding history, payment reference, LMS access, learning record, exam, award or certificate. Synthetic data only.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.base_model import Base
from modules.institutions.models import InstitutionStudent
from modules.internship_learning.award_models import AwardGrant, InternshipAward
from modules.internship_learning.certificate_models import CertificateEligibility, CertificateKind
from modules.internship_learning.models import AssignmentSubmission
from modules.internship_onboarding.models import OnboardingApplication, OnboardingEvent
from modules.our_internships.letter_models import OfferLetter
from modules.our_internships.models import (
    InternshipSelection,
    OfferResponse,
    OfferStatus,
    PaymentStatus,
    VerificationStatus,
)
from modules.our_internships.service import SELECTION_HISTORY_COLUMNS, SELECTION_IDENTITY_COLUMNS, SELECTION_REFERENCING_TABLES
from modules.workshop_exams.models import WorkshopExamAttendee
from tests.api.test_internship_learning import _INTERN, _assignment, _exam, _world

pytestmark = pytest.mark.api


async def _untouched(client, headers, db_session, organization):
    """An internship and the selection of a student nothing has happened to (Ravi: selected, no LMS access, nothing else)."""
    internship, people = await _world(client, headers, db_session, organization)
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(people["ravi@example.com"][0])))).scalar_one()
    return internship, selection, people


async def _remove(client, headers, internship, selection):
    return await client.delete(f"{_INTERN}/{internship['id']}/selected/{selection.student_id}", headers=headers)


async def _exists(db, selection) -> bool:
    return (await db.execute(select(func.count()).select_from(InternshipSelection).where(InternshipSelection.id == selection.id))).scalar_one() == 1


async def test_a_selection_nothing_has_happened_to_can_still_be_removed(client, auth_headers, db_session, organization):
    internship, selection, _ = await _untouched(client, auth_headers, db_session, organization)
    assert (await _remove(client, auth_headers, internship, selection)).status_code == 200
    assert not await _exists(db_session, selection)


# every recorded fact on the selection itself, with a value that records it
_NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)
_FACTS = {
    "note": "called the college",
    "offer_reference": "OFR-1",
    "offer_status": OfferStatus.SENT,
    "offer_sent_at": _NOW,
    "offer_attempts": 1,
    "offer_error": "mailbox full",
    "offer_response": OfferResponse.ACCEPTED,
    "offer_response_at": _NOW,
    "verification_status": VerificationStatus.VERIFIED,
    "verification_note": "documents checked",
    "verified_at": _NOW,
    "payment_status": PaymentStatus.PAID,
    "payment_amount": Decimal("5900.00"),
    "payment_reference": "UPI-123",
    "payment_received_on": date(2026, 11, 2),
    "payment_confirmed_at": _NOW,
    "lms_enrolment_preexisting": True,
    "lms_granted_at": _NOW,
}


@pytest.mark.parametrize("column", sorted(_FACTS))
async def test_any_recorded_fact_on_the_selection_blocks_removal_and_keeps_the_record(client, auth_headers, db_session, organization, column):
    internship, selection, _ = await _untouched(client, auth_headers, db_session, organization)
    setattr(selection, column, _FACTS[column])
    await db_session.flush()
    refused = await _remove(client, auth_headers, internship, selection)
    assert refused.status_code == 409, (column, refused.text)
    assert refused.json()["error"]["details"]["code"] == "has_history"
    assert await _exists(db_session, selection)
    await db_session.refresh(selection)
    assert getattr(selection, column) == _FACTS[column]  # and nothing was changed


@pytest.mark.parametrize("column", ["verified_by_user_id", "payment_confirmed_by_user_id", "lms_user_id", "lms_student_id", "lms_course_id", "lms_granted_by_user_id"])
async def test_a_link_to_an_account_a_course_or_a_person_who_decided_also_blocks_removal(client, auth_headers, db_session, organization, column):
    from tests.api.test_internship_lms_integrity import course_in
    from tests._fixtures import _make_user

    internship, selection, _ = await _untouched(client, auth_headers, db_session, organization)
    if column == "lms_course_id":
        value = (await course_in(db_session, organization)).id
    elif column == "lms_student_id":
        from modules.students.models import Student

        user, _t = await _make_user(db_session, organization, is_superuser=False, email="x@example.com")
        student = Student(organization_id=organization.id, student_code=f"S-{uuid.uuid4().hex[:8]}", full_name="X", email="x@example.com", course_name="C", enrollment_date=date(2026, 1, 1), user_id=user.id)
        db_session.add(student)
        await db_session.flush()
        value = student.id
    else:
        value = (await _make_user(db_session, organization, is_superuser=False, email=f"{column}@example.com"))[0].id
    setattr(selection, column, value)
    await db_session.flush()
    assert (await _remove(client, auth_headers, internship, selection)).status_code == 409
    assert await _exists(db_session, selection)


async def test_a_sent_offer_letter_blocks_removal_and_the_letter_survives(client, auth_headers, db_session, organization):
    internship, selection, _ = await _untouched(client, auth_headers, db_session, organization)
    student = (await db_session.execute(select(InstitutionStudent).where(InstitutionStudent.id == selection.student_id))).scalar_one()
    letter = OfferLetter(organization_id=organization.id, internship_id=uuid.UUID(internship["id"]), selection_id=selection.id, student_id=student.id,
                         reference="OFR-9", student_name=student.name, student_email=student.email, institution_name="College")
    db_session.add(letter)
    await db_session.flush()
    refused = await _remove(client, auth_headers, internship, selection)
    assert refused.status_code == 409 and "offer letter" in refused.text
    await db_session.refresh(letter)
    assert letter.selection_id == selection.id  # not detached either


async def test_a_blank_onboarding_application_holds_nothing_so_removal_is_still_allowed(client, auth_headers, db_session, organization):
    internship, selection, _ = await _untouched(client, auth_headers, db_session, organization)
    db_session.add(OnboardingApplication(organization_id=organization.id, internship_id=uuid.UUID(internship["id"]), selection_id=selection.id, reference="APP-2"))
    await db_session.flush()  # created the first time anyone looked at the student's onboarding
    assert (await _remove(client, auth_headers, internship, selection)).status_code == 200


async def test_an_onboarding_event_is_history_and_survives_the_refusal(client, auth_headers, db_session, organization):
    internship, selection, _ = await _untouched(client, auth_headers, db_session, organization)
    application = OnboardingApplication(organization_id=organization.id, internship_id=uuid.UUID(internship["id"]), selection_id=selection.id, reference="APP-1")
    db_session.add(application)
    await db_session.flush()
    db_session.add(OnboardingEvent(organization_id=organization.id, application_id=application.id, actor="student", event="opened", detail={}))
    await db_session.flush()
    refused = await _remove(client, auth_headers, internship, selection)
    assert refused.status_code == 409 and "onboarding history" in refused.text
    assert (await db_session.execute(select(func.count()).select_from(OnboardingApplication).where(OnboardingApplication.id == application.id))).scalar_one() == 1
    assert (await db_session.execute(select(func.count()).select_from(OnboardingEvent).where(OnboardingEvent.application_id == application.id))).scalar_one() == 1


async def test_accepting_the_terms_or_answering_the_form_is_onboarding_history(client, auth_headers, db_session, organization):
    internship, selection, _ = await _untouched(client, auth_headers, db_session, organization)
    application = OnboardingApplication(organization_id=organization.id, internship_id=uuid.UUID(internship["id"]), selection_id=selection.id, reference="APP-3", accepted_at=_NOW)
    db_session.add(application)
    await db_session.flush()
    assert (await _remove(client, auth_headers, internship, selection)).status_code == 409
    application.accepted_at = None
    application.form_responses = {"college": "X"}
    await db_session.flush()
    assert (await _remove(client, auth_headers, internship, selection)).status_code == 409


async def test_learning_records_awards_certificates_and_exam_places_block_removal(client, auth_headers, db_session, organization):
    internship, selection, _ = await _untouched(client, auth_headers, db_session, organization)
    iid = uuid.UUID(internship["id"])

    async def blocked() -> None:
        assert (await _remove(client, auth_headers, internship, selection)).status_code == 409
        assert await _exists(db_session, selection)

    award = InternshipAward(organization_id=organization.id, internship_id=iid, name="Best")
    db_session.add(award)
    await db_session.flush()
    grant = AwardGrant(organization_id=organization.id, award_id=award.id, selection_id=selection.id, granted_at=_NOW)
    db_session.add(grant)
    await db_session.flush()
    await blocked()
    await db_session.delete(grant)
    await db_session.flush()

    kinds = list(CertificateKind)
    cert = CertificateEligibility(organization_id=organization.id, internship_id=iid, selection_id=selection.id, kind=kinds[0], chosen_at=_NOW)
    db_session.add(cert)
    await db_session.flush()
    await blocked()
    await db_session.delete(cert)
    await db_session.flush()

    assignment = await _assignment(client, auth_headers, internship)
    submission = AssignmentSubmission(organization_id=organization.id, assignment_id=uuid.UUID(assignment["id"]), selection_id=selection.id, submitted_at=_NOW)
    db_session.add(submission)
    await db_session.flush()
    await blocked()
    await db_session.delete(submission)
    await db_session.flush()

    exam = await _exam(client, auth_headers, internship)
    attendee = WorkshopExamAttendee(exam_id=uuid.UUID(exam["id"]), name="Ravi", email="ravi@example.com", access_token=uuid.uuid4().hex, selection_id=selection.id)
    db_session.add(attendee)
    await db_session.flush()
    await blocked()
    await db_session.delete(attendee)
    await db_session.flush()

    assert (await _remove(client, auth_headers, internship, selection)).status_code == 200  # every record gone, so nothing is lost now


async def test_the_refusal_says_why_and_points_at_the_safe_alternative(client, auth_headers, db_session, organization):
    internship, selection, _ = await _untouched(client, auth_headers, db_session, organization)
    selection.offer_status = OfferStatus.SENT
    selection.payment_reference = "UPI-1"
    await db_session.flush()
    body = (await _remove(client, auth_headers, internship, selection)).json()["error"]
    assert "offer letter was sent or attempted" in body["message"] and "payment reference" in body["message"]
    assert "Their records are kept" in body["message"]
    assert len(body["details"]["reasons"]) == len(set(body["details"]["reasons"]))  # no repeats


# ------------------------------------------------------------ so the audit cannot silently go stale


def test_every_column_of_a_selection_is_classified_as_history_or_identity():
    columns = {c.name for c in InternshipSelection.__table__.columns}
    classified = set(SELECTION_HISTORY_COLUMNS) | SELECTION_IDENTITY_COLUMNS
    assert columns == classified, f"a new column needs a decision (history or identity): {sorted(columns ^ classified)}"


def test_every_table_that_points_at_a_selection_is_checked_before_removal():
    import modules.institutions.models  # noqa: F401  (load every model so the metadata is complete)
    import modules.internship_learning.award_models  # noqa: F401
    import modules.internship_learning.certificate_models  # noqa: F401
    import modules.internship_learning.models  # noqa: F401
    import modules.internship_learning.project_models  # noqa: F401
    import modules.internship_onboarding.models  # noqa: F401
    import modules.our_internships.letter_models  # noqa: F401
    import modules.workshop_exams.models  # noqa: F401

    referencing = {
        table.name
        for table in Base.metadata.tables.values()
        for fk in table.foreign_keys
        if fk.column.table.name == "our_internship_selections"
    }
    assert referencing == SELECTION_REFERENCING_TABLES, f"a table now references selections and history_of must check it: {sorted(referencing ^ SELECTION_REFERENCING_TABLES)}"


async def test_an_offer_released_but_not_yet_delivered_does_not_block_removal_but_a_delivery_attempt_does(client, auth_headers, db_session, organization):
    internship, selection, _ = await _untouched(client, auth_headers, db_session, organization)
    selection.offer_status = OfferStatus.QUEUED
    selection.offer_reference = "OFR-2026-ABCD-001"  # reserved when the offer was released; nothing has reached the student
    await db_session.flush()
    assert (await _remove(client, auth_headers, internship, selection)).status_code == 200


async def test_a_queued_offer_that_was_attempted_or_failed_is_history(client, auth_headers, db_session, organization):
    internship, selection, _ = await _untouched(client, auth_headers, db_session, organization)
    selection.offer_status = OfferStatus.QUEUED
    selection.offer_reference = "OFR-2026-ABCD-002"
    selection.offer_attempts = 1
    await db_session.flush()
    assert (await _remove(client, auth_headers, internship, selection)).status_code == 409
