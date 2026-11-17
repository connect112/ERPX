"""
The read-only production preflight for migrations 0104/0106 (ops/preflight/0104_0106_lms_access_ambiguity.sql): it must be read-only,
and it must flag exactly the records where the 0104 backfill (which copies the internship's CURRENT course onto students who already
have or had access) can be wrong, and the enrolments that predate a grant. Synthetic data only.
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, text, update

from modules.audit.models import AuditLog
from modules.lms.enrollment.models import Enrollment
from modules.our_internships.models import InternshipSelection
from tests.api.test_internship_lms_independent_enrolment import independent_student, selection_of
from tests.api.test_internship_lms_integrity import course_in, grant, ready
from tests.api.test_internship_onboarding import world

pytestmark = pytest.mark.api

SQL_FILE = Path(__file__).resolve().parents[2] / "ops/preflight/0104_0106_lms_access_ambiguity.sql"


def statements() -> list[str]:
    """The file's SELECT statements (comments and the BEGIN/ROLLBACK lines removed)."""
    lines = [line for line in SQL_FILE.read_text(encoding="utf8").splitlines() if not line.strip().startswith("--")]
    body = "\n".join(lines)
    parts = [p.strip() for p in body.split(";") if p.strip()]
    return [p for p in parts if p.upper() not in ("BEGIN TRANSACTION READ ONLY", "ROLLBACK")]


async def run_all(db) -> list[list[dict]]:
    out = []
    for sql in statements():
        out.append([dict(r._mapping) for r in (await db.execute(text(sql))).all()])
    return out


def test_the_preflight_cannot_write():
    raw = SQL_FILE.read_text(encoding="utf8")
    code = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("--"))
    assert "BEGIN TRANSACTION READ ONLY" in code and code.rstrip().endswith("ROLLBACK;")
    for part in statements():
        assert part.upper().lstrip().startswith("SELECT"), part[:60]
    no_literals = re.sub(r"'[^']*'", "''", code)  # the word 'update' inside a string (an audit action) is not a statement
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY|VACUUM)\b", no_literals, re.IGNORECASE)
    assert not re.search(r"\b(email|phone|password|token|full_name)\b", code, re.IGNORECASE)  # ids and titles only


async def test_it_runs_on_an_empty_database_and_returns_nothing(db_session):
    assert await run_all(db_session) == [[], [], [], []]


async def test_it_flags_a_relinked_internship_and_an_enrolment_that_predates_the_grant_and_nothing_else(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, s1) = await world(db_session, organization)
    other_internship, (t0, _) = await world(db_session, organization)
    first = await course_in(db_session, organization, title="First course")
    second = await course_in(db_session, organization, title="Second course")
    internship.lms_course_id = first.id
    other_internship.lms_course_id = first.id
    # s1 was enrolled in the course on their own, 30 days before the internship gave them access
    _, _, own = await independent_student(client, db_session, organization, s1, first)
    await db_session.flush()
    for i, s in ((internship, s0), (internship, s1), (other_internship, t0)):
        await ready(db_session, i, s)
        assert (await grant(client, auth_headers, i, s)).status_code == 200
    long_ago = datetime.now(timezone.utc) - timedelta(days=30)
    await db_session.execute(update(Enrollment).where(Enrollment.id == own.id).values(created_at=long_ago))
    # every other enrolment was made by its grant, at the moment of the grant
    for i, s in ((internship, s0), (other_internship, t0)):
        sel = await selection_of(db_session, i, s)
        await db_session.execute(update(Enrollment).where(Enrollment.student_id == sel.lms_student_id).values(created_at=sel.lms_granted_at))
    await db_session.flush()

    # master let an administrator change the course at any time: this internship is relinked AFTER its students were given access
    internship.lms_course_id = second.id
    await db_session.flush()  # the audit trail records first -> second, as it does in production
    await db_session.execute(
        update(AuditLog)
        .where(AuditLog.entity_type == "our_internships", AuditLog.entity_id == internship.id, AuditLog.changes["lms_course_id"]["old"].as_string().is_not(None))
        .values(created_at=datetime.now(timezone.utc) + timedelta(minutes=5))  # (in this test everything shares one transaction timestamp)
    )
    await db_session.flush()

    relinks, after_grant, not_in_current, predate = await run_all(db_session)

    assert [(r["internship_id"], r["old_course_id"], r["new_course_id"]) for r in relinks] == [(internship.id, str(first.id), str(second.id))]
    flagged = {r["selection_id"] for r in after_grant}
    sel0 = await selection_of(db_session, internship, s0)
    sel1 = await selection_of(db_session, internship, s1)
    assert flagged == {sel0.id, sel1.id}  # both were granted before the relink; the other internship was never relinked
    assert {r["selection_id"] for r in not_in_current} == {sel0.id, sel1.id}  # and neither holds an enrolment in the course it now points at
    assert all(r["why"] == "no live enrolment in the current course" for r in not_in_current)
    assert predate == []  # section 4 joins on the course the internship has now: nobody holds an enrolment in the new course


async def test_a_grant_that_created_its_enrolment_and_an_internship_that_was_never_relinked_are_not_flagged(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, s1) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    internship.lms_course_id = course.id
    _, _, own = await independent_student(client, db_session, organization, s1, course)
    await db_session.flush()
    for s in (s0, s1):
        await ready(db_session, internship, s)
        assert (await grant(client, auth_headers, internship, s)).status_code == 200
    await db_session.execute(update(Enrollment).where(Enrollment.id == own.id).values(created_at=datetime.now(timezone.utc) - timedelta(days=30)))
    sel0 = await selection_of(db_session, internship, s0)
    await db_session.execute(update(Enrollment).where(Enrollment.student_id == sel0.lms_student_id).values(created_at=sel0.lms_granted_at))
    await db_session.flush()

    relinks, after_grant, not_in_current, predate = await run_all(db_session)
    assert relinks == [] and after_grant == [] and not_in_current == []
    sel1 = await selection_of(db_session, internship, s1)
    assert [r["selection_id"] for r in predate] == [sel1.id]  # only the student who was enrolled before the grant
    assert isinstance(sel1, InternshipSelection)
