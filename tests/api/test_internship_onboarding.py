"""
Onboarding after the offers: verification, manually confirmed payment, and LMS access.

LMS access is the one thing that creates or changes accounts, so most of the care here is about the cases that could hand
access to the wrong person or leave a half-made account: a student with no account, one who already has a student account
(for example from a hackathon), an email that belongs to staff, and giving access twice or taking it back.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from modules.authentication.repository import AuthRepository
from modules.authorization.models import Role, UserRole
from modules.batches.models import BatchEnrollment
from modules.batches.repository import BatchRepository
from modules.courses.repository import CourseRepository
from modules.lms.enrollment.models import Enrollment, EnrollmentStatus
from modules.organizations.repository import OrganizationRepository
from modules.our_internships import onboarding
from modules.our_internships.models import InternshipSelection, LmsStatus
from modules.students.models import Student
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

_INST = "/api/v1/institutions"
_EVENTS = "/api/v1/institution-events"
_INTERN = "/api/v1/our-internships"
_LIST = "Name,Email,Phone\nAsha Rao,asha@example.com,9876543210\nMeera Iyer,meera@example.com,9123456789\nRavi Kumar,ravi@example.com,9000011111\n"


class FakeTask:
    """Stands in for the set-password email task, recording who was sent a link."""

    def __init__(self):
        self.sent: list[tuple] = []

    def delay(self, *args):
        self.sent.append(args)


class Mailbox:
    def __init__(self):
        self.sent: list[tuple] = []

    async def send(self, to, subject, text, html=None, attachments=None):
        self.sent.append((to, subject, text))
        return True


@pytest.fixture
def invites(monkeypatch):
    fake = FakeTask()
    monkeypatch.setattr(onboarding, "send_password_reset_email_task", fake)
    return fake


@pytest.fixture
def mailbox(monkeypatch):
    box = Mailbox()
    monkeypatch.setattr(onboarding.email_service, "send", box.send)
    return box


@pytest.fixture
async def course(db_session, organization, rbac_seeded):
    created = await CourseRepository(db_session).create(
        organization_id=organization.id, title="Pentrix Cyber Internship Course", slug=f"cyber-{uuid.uuid4().hex[:6]}", is_published=True
    )
    await db_session.flush()
    return created


async def _setup(client, headers, emails=("asha@example.com", "meera@example.com", "ravi@example.com")):
    inst = (await client.post(_INST, json={"name": "Sri Venkateswara College", "location": "Tirupati", "faculty_name": "Dr. L"}, headers=headers)).json()
    event = (
        await client.post(
            f"{_INST}/{inst['id']}/events",
            json={"name": "Workshop", "event_type": "workshop", "start_date": "2026-11-10", "end_date": "2026-11-11"},
            headers=headers,
        )
    ).json()
    await client.post(f"{_EVENTS}/{event['id']}/students/import", data={"text": _LIST}, headers=headers)
    internship = (await client.post(_INTERN, json={"title": "Pentrix Cyber Internship", "scope": "all"}, headers=headers)).json()
    board = (await client.get(f"{_INTERN}/{internship['id']}/performance", headers=headers)).json()
    ids = {s["email"]: s["student_id"] for s in board["students"]}
    r = await client.post(f"{_INTERN}/{internship['id']}/selected", json={"student_ids": [ids[e] for e in emails]}, headers=headers)
    assert r.status_code == 200, r.text
    return internship, ids


async def _course_on(client, headers, internship, course):
    r = await client.patch(f"{_INTERN}/{internship['id']}", json={"lms_course_id": str(course.id)}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _mark(client, headers, internship, student_id, **fields):
    return await client.patch(f"{_INTERN}/{internship['id']}/selected/{student_id}/onboarding", json=fields, headers=headers)


async def _earn(client, headers, internship, student_id):
    """Verified and paid: everything needed for LMS access except the course."""
    r = await _mark(client, headers, internship, student_id, verification_status="verified", payment_status="paid")
    assert r.status_code == 200, r.text
    return r.json()


async def _grant(client, headers, internship, student_id):
    return await client.post(f"{_INTERN}/{internship['id']}/selected/{student_id}/lms/grant", headers=headers)


async def _profile(client, headers, internship, student_id):
    return (await client.get(f"{_INTERN}/{internship['id']}/selected/{student_id}", headers=headers)).json()


async def _roles_of(db_session, user_id) -> set[str]:
    rows = await db_session.execute(select(Role.slug).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id))
    return {slug for (slug,) in rows.all()}


# ------------------------------------------------------------ where each student is


async def test_a_student_moves_through_the_stages_as_each_step_is_recorded(client, auth_headers, db_session):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    assert (await _profile(client, auth_headers, internship, sid))["stage"] == "selected"

    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == uuid.UUID(sid)))).scalar_one()
    from modules.our_internships.models import OfferStatus

    selection.offer_status = OfferStatus.SENT
    await db_session.flush()
    assert (await _profile(client, auth_headers, internship, sid))["stage"] == "offer_sent"

    accepted = (await _mark(client, auth_headers, internship, sid, offer_response="accepted")).json()
    assert (accepted["stage"], accepted["stage_label"], accepted["offer_response_at"] is not None) == ("accepted", "Offer accepted", True)
    assert (await _mark(client, auth_headers, internship, sid, verification_status="verified")).json()["stage"] == "verified"
    paid = (await _mark(client, auth_headers, internship, sid, payment_status="paid")).json()
    assert paid["stage"] == "ready_for_lms"
    # undoing a step moves the student back
    assert (await _mark(client, auth_headers, internship, sid, payment_status="pending")).json()["stage"] == "verified"


async def test_declining_or_failing_verification_is_its_own_stage_and_can_be_undone(client, auth_headers):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    assert (await _mark(client, auth_headers, internship, sid, offer_response="declined")).json()["stage"] == "declined"
    assert (await _mark(client, auth_headers, internship, sid, offer_response="awaiting")).json()["offer_response_at"] is None
    failed = (await _mark(client, auth_headers, internship, sid, verification_status="rejected", verification_note="  Marksheet does not match  ")).json()
    assert (failed["stage"], failed["verification_note"]) == ("rejected", "Marksheet does not match")
    assert (await _mark(client, auth_headers, internship, sid, verification_status="pending")).json()["verified_at"] is None


async def test_verification_and_payment_record_the_details_staff_give(client, auth_headers):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["meera@example.com"]
    done = (
        await _mark(
            client, auth_headers, internship, sid,
            payment_status="paid", payment_amount="4999.50", payment_reference="  UTR 4412  ", payment_received_on="2026-11-18",
        )
    ).json()
    assert (done["payment_status"], done["payment_amount"], done["payment_reference"], done["payment_received_on"]) == ("paid", 4999.5, "UTR 4412", "2026-11-18")
    assert done["payment_confirmed_at"] is not None
    # an amount can be corrected without touching the status; a missing date defaults to today when marking paid
    assert (await _mark(client, auth_headers, internship, sid, payment_amount="5000")).json()["payment_amount"] == 5000.0
    other = (await _mark(client, auth_headers, internship, ids["asha@example.com"], payment_status="paid")).json()
    assert other["payment_received_on"] == date.today().isoformat()
    assert (await _mark(client, auth_headers, internship, sid, payment_status="pending")).json()["payment_confirmed_at"] is None


async def test_bad_values_are_refused(client, auth_headers):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    for body in ({"payment_amount": "-1"}, {"payment_status": "refunded"}, {"verification_status": None}, {"offer_response": "maybe"}):
        r = await _mark(client, auth_headers, internship, sid, **body)
        assert r.status_code == 422, (body, r.text)
    nobody = await _mark(client, auth_headers, internship, str(uuid.uuid4()), payment_status="paid")
    assert nobody.status_code == 404


# ------------------------------------------------------------------ the LMS course


async def test_the_lms_course_is_chosen_changed_and_cleared(client, auth_headers, course):
    internship, _ = await _setup(client, auth_headers)
    listed = (await client.get(f"{_INTERN}/{internship['id']}/lms/courses", headers=auth_headers)).json()
    assert [c["id"] for c in listed] == [str(course.id)]
    chosen = await _course_on(client, auth_headers, internship, course)
    assert (chosen["lms_course_id"], chosen["lms_course_title"]) == (str(course.id), "Pentrix Cyber Internship Course")
    cleared = await client.patch(f"{_INTERN}/{internship['id']}", json={"lms_course_id": None}, headers=auth_headers)
    assert cleared.json()["lms_course_id"] is None
    assert (await client.patch(f"{_INTERN}/{internship['id']}", json={"lms_course_id": str(uuid.uuid4())}, headers=auth_headers)).status_code == 404


async def test_another_organizations_course_cannot_be_used(client, auth_headers, db_session, rbac_seeded):
    internship, _ = await _setup(client, auth_headers)
    other_org = await OrganizationRepository(db_session).create(name="Rival Org", slug=f"rival-{uuid.uuid4().hex[:6]}")
    foreign = await CourseRepository(db_session).create(organization_id=other_org.id, title="Rival course", slug=f"r-{uuid.uuid4().hex[:6]}", is_published=True)
    await db_session.flush()
    assert (await client.patch(f"{_INTERN}/{internship['id']}", json={"lms_course_id": str(foreign.id)}, headers=auth_headers)).status_code == 404
    assert [c["title"] for c in (await client.get(f"{_INTERN}/{internship['id']}/lms/courses", headers=auth_headers)).json()] == []


# ------------------------------------------------------------------ granting access


async def test_access_is_blocked_until_the_course_is_chosen_and_both_checks_are_done(client, auth_headers, course, invites):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    blockers = (await _profile(client, auth_headers, internship, sid))["grant_blockers"]
    assert blockers == ["Choose the LMS course for this internship first.", "Verification is not complete.", "Payment has not been confirmed."]
    refused = await _grant(client, auth_headers, internship, sid)
    assert refused.status_code == 422 and "Verification is not complete." in refused.json()["error"]["message"]

    await _course_on(client, auth_headers, internship, course)
    await _mark(client, auth_headers, internship, sid, verification_status="verified")
    assert (await _profile(client, auth_headers, internship, sid))["grant_blockers"] == ["Payment has not been confirmed."]
    await _mark(client, auth_headers, internship, sid, payment_status="paid", offer_response="declined")
    assert (await _profile(client, auth_headers, internship, sid))["grant_blockers"] == ["The student declined the offer."]
    assert (await _grant(client, auth_headers, internship, sid)).status_code == 422
    assert invites.sent == []


async def test_a_new_student_gets_an_account_a_student_record_an_enrolment_and_a_set_password_link(client, auth_headers, db_session, course, invites):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    await _course_on(client, auth_headers, internship, course)
    await _earn(client, auth_headers, internship, sid)

    r = await _grant(client, auth_headers, internship, sid)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["stage"], body["lms_status"], body["grant_blockers"]) == ("lms_access", "granted", ["LMS access has already been granted."])

    user = await AuthRepository(db_session).get_user_by_email("asha@example.com")
    assert user is not None and user.is_email_verified and user.status.value == "active"
    student = (await db_session.execute(select(Student).where(Student.user_id == user.id))).scalar_one()
    assert (student.full_name, student.email, student.phone, student.organization_id) == ("Asha Rao", "asha@example.com", "9876543210", course.organization_id)
    enrollment = (await db_session.execute(select(Enrollment).where(Enrollment.student_id == student.id))).scalar_one()
    assert (enrollment.course_id, enrollment.status) == (course.id, EnrollmentStatus.ACTIVE)
    assert "student" in await _roles_of(db_session, user.id)
    # one set-password email, to that address, never a password
    assert len(invites.sent) == 1
    email, name, link, kind = invites.sent[0]
    assert (email, name, kind) == ("asha@example.com", "Asha Rao", "account_invite") and "reset-password?token=" in link

    row = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == uuid.UUID(sid)))).scalar_one()
    assert (row.lms_user_id, row.lms_student_id, row.lms_granted_at is not None) == (user.id, student.id, True)


async def test_granting_twice_does_not_create_a_second_account_or_email(client, auth_headers, db_session, course, invites):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    await _course_on(client, auth_headers, internship, course)
    await _earn(client, auth_headers, internship, sid)
    assert (await _grant(client, auth_headers, internship, sid)).status_code == 200
    again = await _grant(client, auth_headers, internship, sid)
    assert again.status_code == 422 and "already been granted" in again.json()["error"]["message"]
    assert len(invites.sent) == 1
    assert len((await db_session.execute(select(Student).where(Student.email == "asha@example.com"))).scalars().all()) == 1


async def test_someone_who_already_has_a_student_account_is_enrolled_not_duplicated(client, auth_headers, db_session, organization, course, invites, mailbox):
    """For example a hackathon participant: a student account with only the restricted role."""
    internship, ids = await _setup(client, auth_headers)
    sid = ids["meera@example.com"]
    user, _ = await _make_user(db_session, organization, is_superuser=False, email="meera@example.com")
    participant_role = (await db_session.execute(select(Role).where(Role.slug == "hackathon_participant"))).scalar_one()
    db_session.add(UserRole(user_id=user.id, role_id=participant_role.id))
    existing = Student(organization_id=organization.id, student_code=f"S-{uuid.uuid4().hex[:8]}", full_name="Meera Iyer", email="meera@example.com",
                       user_id=user.id, course_name="Hackathon", enrollment_date=date(2026, 1, 1))
    db_session.add(existing)
    await db_session.flush()
    await _course_on(client, auth_headers, internship, course)
    await _earn(client, auth_headers, internship, sid)

    assert (await _grant(client, auth_headers, internship, sid)).status_code == 200
    students = (await db_session.execute(select(Student).where(Student.email == "meera@example.com"))).scalars().all()
    assert [s.id for s in students] == [existing.id]
    assert {"hackathon_participant", "student"} <= await _roles_of(db_session, user.id)
    assert (await db_session.execute(select(Enrollment).where(Enrollment.student_id == existing.id, Enrollment.course_id == course.id))).scalar_one()
    # an existing account gets a short note rather than a new set-password link
    assert invites.sent == []
    assert mailbox.sent[0][0] == "meera@example.com" and "Pentrix Cyber Internship Course" in mailbox.sent[0][2]


async def test_an_email_that_belongs_to_staff_is_never_given_student_access(client, auth_headers, db_session, organization, course, invites, mailbox):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["ravi@example.com"]
    staff, _ = await _make_user(db_session, organization, is_superuser=False, email="ravi@example.com")
    await _course_on(client, auth_headers, internship, course)
    await _earn(client, auth_headers, internship, sid)
    r = await _grant(client, auth_headers, internship, sid)
    assert r.status_code == 409 and "not a student account" in r.json()["error"]["message"]
    assert (await _profile(client, auth_headers, internship, sid))["lms_status"] == "not_granted"
    assert "student" not in await _roles_of(db_session, staff.id)
    assert (await db_session.execute(select(Student).where(Student.email == "ravi@example.com"))).first() is None
    assert invites.sent == [] and mailbox.sent == []


async def test_a_student_record_with_no_login_is_reused_and_linked_to_the_new_account(client, auth_headers, db_session, organization, course, invites):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    unlinked = Student(organization_id=organization.id, student_code=f"S-{uuid.uuid4().hex[:8]}", full_name="Asha R.", email="Asha@Example.com",
                       course_name="Workshop", enrollment_date=date(2026, 1, 1))
    db_session.add(unlinked)
    await db_session.flush()
    await _course_on(client, auth_headers, internship, course)
    await _earn(client, auth_headers, internship, sid)
    assert (await _grant(client, auth_headers, internship, sid)).status_code == 200
    await db_session.refresh(unlinked)
    user = await AuthRepository(db_session).get_user_by_email("asha@example.com")
    assert unlinked.user_id == user.id
    assert len((await db_session.execute(select(Student).where(Student.organization_id == organization.id))).scalars().all()) == 1


async def test_a_new_student_joins_the_courses_first_batch_when_it_has_one(client, auth_headers, db_session, organization, course, invites):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    batch = await BatchRepository(db_session).create(organization_id=organization.id, course_id=course.id, name="Batch 1", code="B1", start_date=date(2026, 12, 1))
    await _course_on(client, auth_headers, internship, course)
    await _earn(client, auth_headers, internship, sid)
    await _grant(client, auth_headers, internship, sid)
    student = (await db_session.execute(select(Student).where(Student.email == "asha@example.com"))).scalar_one()
    assert (await db_session.execute(select(BatchEnrollment).where(BatchEnrollment.student_id == student.id, BatchEnrollment.batch_id == batch.id))).scalar_one()


# ---------------------------------------------------------------- taking it back


async def test_access_can_be_withdrawn_and_granted_again_without_duplicates(client, auth_headers, db_session, course, invites):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    await _course_on(client, auth_headers, internship, course)
    await _earn(client, auth_headers, internship, sid)
    await _grant(client, auth_headers, internship, sid)
    student = (await db_session.execute(select(Student).where(Student.email == "asha@example.com"))).scalar_one()

    revoked = await client.post(f"{_INTERN}/{internship['id']}/selected/{sid}/lms/revoke", headers=auth_headers)
    assert revoked.status_code == 200 and revoked.json()["lms_status"] == "revoked"
    enrollment = (await db_session.execute(select(Enrollment).where(Enrollment.student_id == student.id))).scalar_one()
    assert enrollment.status == EnrollmentStatus.DROPPED
    # the account itself is left alone
    assert await AuthRepository(db_session).get_user_by_email("asha@example.com") is not None
    assert (await client.post(f"{_INTERN}/{internship['id']}/selected/{sid}/lms/revoke", headers=auth_headers)).status_code == 422

    again = await _grant(client, auth_headers, internship, sid)
    assert again.status_code == 200 and again.json()["lms_status"] == "granted"
    await db_session.refresh(enrollment)
    assert enrollment.status == EnrollmentStatus.ACTIVE
    assert len((await db_session.execute(select(Enrollment).where(Enrollment.student_id == student.id))).scalars().all()) == 1
    assert len((await db_session.execute(select(Student).where(Student.email == "asha@example.com"))).scalars().all()) == 1


async def test_verification_and_payment_cannot_be_undone_while_the_student_has_access(client, auth_headers, course, invites):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    await _course_on(client, auth_headers, internship, course)
    await _earn(client, auth_headers, internship, sid)
    await _grant(client, auth_headers, internship, sid)
    for body in ({"verification_status": "pending"}, {"payment_status": "pending"}, {"verification_status": "rejected"}):
        r = await _mark(client, auth_headers, internship, sid, **body)
        assert r.status_code == 409 and "Revoke it" in r.json()["error"]["message"], body
    # notes and the offer response can still be edited
    assert (await _mark(client, auth_headers, internship, sid, verification_note="Documents re-checked")).status_code == 200
    await client.post(f"{_INTERN}/{internship['id']}/selected/{sid}/lms/revoke", headers=auth_headers)
    assert (await _mark(client, auth_headers, internship, sid, payment_status="pending")).status_code == 200


# ---------------------------------------------------------------------- in bulk


async def test_several_students_can_be_marked_at_once_and_one_that_cannot_is_reported(client, auth_headers, course, invites):
    internship, ids = await _setup(client, auth_headers)
    await _course_on(client, auth_headers, internship, course)
    await _earn(client, auth_headers, internship, ids["asha@example.com"])
    await _grant(client, auth_headers, internship, ids["asha@example.com"])

    r = await client.post(
        f"{_INTERN}/{internship['id']}/onboarding/bulk",
        json={"student_ids": list(ids.values()), "verification_status": "pending"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["changed"] == 2  # the two who could take the change; asha, who has access, is reported below
    assert len(r.json()["problems"]) == 1 and r.json()["problems"][0].startswith("Asha Rao:")
    verified = await client.post(
        f"{_INTERN}/{internship['id']}/onboarding/bulk",
        json={"student_ids": [ids["meera@example.com"], ids["ravi@example.com"]], "verification_status": "verified", "payment_status": "paid"},
        headers=auth_headers,
    )
    assert (verified.json()["changed"], verified.json()["problems"]) == (2, [])
    assert (await _profile(client, auth_headers, internship, ids["ravi@example.com"]))["stage"] == "ready_for_lms"
    nothing = await client.post(f"{_INTERN}/{internship['id']}/onboarding/bulk", json={"student_ids": [ids["ravi@example.com"]]}, headers=auth_headers)
    assert nothing.status_code == 422
    not_selected = await client.post(
        f"{_INTERN}/{internship['id']}/onboarding/bulk", json={"student_ids": [str(uuid.uuid4())], "payment_status": "paid"}, headers=auth_headers
    )
    assert not_selected.status_code == 422


async def test_access_can_be_granted_to_several_students_and_those_not_ready_are_reported(client, auth_headers, db_session, course, invites):
    internship, ids = await _setup(client, auth_headers)
    await _course_on(client, auth_headers, internship, course)
    await _earn(client, auth_headers, internship, ids["asha@example.com"])
    await _earn(client, auth_headers, internship, ids["meera@example.com"])  # ravi is not verified or paid
    r = await client.post(f"{_INTERN}/{internship['id']}/lms/grant", json={"student_ids": list(ids.values())}, headers=auth_headers)
    assert r.status_code == 200, r.text
    results = {x["name"]: x for x in r.json()["results"]}
    assert r.json()["granted"] == 2
    assert results["Asha Rao"]["ok"] and results["Meera Iyer"]["ok"]
    assert not results["Ravi Kumar"]["ok"] and "Verification is not complete." in results["Ravi Kumar"]["message"]
    assert {i[0] for i in invites.sent} == {"asha@example.com", "meera@example.com"}
    assert await AuthRepository(db_session).get_user_by_email("ravi@example.com") is None
    assert (await _profile(client, auth_headers, internship, ids["ravi@example.com"]))["lms_status"] == "not_granted"


async def test_one_bad_student_in_a_bulk_grant_leaves_no_half_made_account(client, auth_headers, db_session, organization, course, invites):
    internship, ids = await _setup(client, auth_headers)
    await _course_on(client, auth_headers, internship, course)
    for email in ("asha@example.com", "ravi@example.com"):
        await _earn(client, auth_headers, internship, ids[email])
    await _make_user(db_session, organization, is_superuser=False, email="asha@example.com")  # staff address: refused
    r = await client.post(f"{_INTERN}/{internship['id']}/lms/grant", json={"student_ids": [ids["asha@example.com"], ids["ravi@example.com"]]}, headers=auth_headers)
    results = {x["name"]: x for x in r.json()["results"]}
    assert (results["Asha Rao"]["ok"], results["Ravi Kumar"]["ok"]) == (False, True)
    assert "not a student account" in results["Asha Rao"]["message"]
    assert (await db_session.execute(select(Student).where(Student.email == "asha@example.com"))).first() is None
    assert (await db_session.execute(select(Student).where(Student.email == "ravi@example.com"))).scalar_one()


async def test_a_bulk_grant_is_limited_to_25_students(client, auth_headers, course):
    internship, _ = await _setup(client, auth_headers)
    r = await client.post(f"{_INTERN}/{internship['id']}/lms/grant", json={"student_ids": [str(uuid.uuid4()) for _ in range(26)]}, headers=auth_headers)
    assert r.status_code == 422


# ------------------------------------------------------------------------ access


async def test_without_the_permission_onboarding_is_not_reachable(client, auth_headers, staff_headers):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    base = f"{_INTERN}/{internship['id']}"
    for method, url, kwargs in (
        ("get", f"{base}/selected/{sid}", {}),
        ("get", f"{base}/lms/courses", {}),
        ("patch", f"{base}/selected/{sid}/onboarding", {"json": {"payment_status": "paid"}}),
        ("post", f"{base}/onboarding/bulk", {"json": {"student_ids": [sid], "payment_status": "paid"}}),
        ("post", f"{base}/selected/{sid}/lms/grant", {}),
        ("post", f"{base}/lms/grant", {"json": {"student_ids": [sid]}}),
        ("post", f"{base}/selected/{sid}/lms/revoke", {}),
    ):
        r = await getattr(client, method)(url, headers=staff_headers, **kwargs)
        assert r.status_code == 403, (method, url, r.status_code)


async def test_another_organization_cannot_change_or_grant(client, auth_headers, db_session, course, invites):
    internship, ids = await _setup(client, auth_headers)
    sid = ids["asha@example.com"]
    await _course_on(client, auth_headers, internship, course)
    await _earn(client, auth_headers, internship, sid)
    other = await OrganizationRepository(db_session).create(name="Rival Org", slug=f"rival-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other, is_superuser=True, email=f"rival-{uuid.uuid4().hex[:6]}@example.com")
    rival = {"Authorization": f"Bearer {token}"}
    base = f"{_INTERN}/{internship['id']}"
    for method, url, kwargs in (
        ("get", f"{base}/selected/{sid}", {}),
        ("patch", f"{base}/selected/{sid}/onboarding", {"json": {"payment_status": "pending"}}),
        ("post", f"{base}/selected/{sid}/lms/grant", {}),
        ("post", f"{base}/lms/grant", {"json": {"student_ids": [sid]}}),
        ("post", f"{base}/onboarding/bulk", {"json": {"student_ids": [sid], "payment_status": "pending"}}),
    ):
        assert (await getattr(client, method)(url, headers=rival, **kwargs)).status_code == 404, (method, url)
    assert invites.sent == []
    assert (await _profile(client, auth_headers, internship, sid))["payment_status"] == "paid"
    row = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == uuid.UUID(sid)))).scalar_one()
    assert row.lms_status == LmsStatus.NOT_GRANTED
