"""
The read-only production preflight for migration 0107 (ops/preflight/0107_learning_integration.sql): it must be read-only, it must run on
an empty database, and it must flag exactly the exam attendees the selection backfill will not link and the ones whose personal link
stops working with the release. Synthetic data only.
"""

import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text

from modules.our_internships.models import InternshipSelection, LmsStatus
from modules.workshop_exams.models import WorkshopExamAttendee
from tests.api.test_internship_learning import _EXAMS, _INTERN, _exam, _world

pytestmark = pytest.mark.api

SQL_FILE = Path(__file__).resolve().parents[2] / "ops/preflight/0107_learning_integration.sql"


def statements() -> list[str]:
    lines = [line for line in SQL_FILE.read_text(encoding="utf8").splitlines() if not line.strip().startswith("--")]
    parts = [p.strip() for p in "\n".join(lines).split(";") if p.strip()]
    return [p for p in parts if p.upper() not in ("BEGIN TRANSACTION READ ONLY", "ROLLBACK")]


async def run_all(db) -> list[list[dict]]:
    return [[dict(r._mapping) for r in (await db.execute(text(sql))).all()] for sql in statements()]


def test_the_preflight_cannot_write():
    raw = SQL_FILE.read_text(encoding="utf8")
    code = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("--"))
    assert "BEGIN TRANSACTION READ ONLY" in code and code.rstrip().endswith("ROLLBACK;")
    for part in statements():
        assert part.upper().lstrip().startswith("SELECT"), part[:60]
    no_literals = re.sub(r"'[^']*'", "''", code)
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY|VACUUM)\b", no_literals, re.IGNORECASE)
    assert not re.search(r"\b(phone|password|token|full_name)\b", code, re.IGNORECASE)


async def test_it_runs_on_an_empty_database_and_returns_nothing(db_session):
    assert await run_all(db_session) == [[], [], [], []]


async def test_it_never_returns_a_person_or_an_address(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    await _exam(client, auth_headers, internship)
    for rows in await run_all(db_session):
        for row in rows:
            assert not ({"email", "name", "phone", "full_name"} & set(row))


async def test_it_flags_an_unmatched_attendee_and_one_whose_link_will_stop_and_nothing_else(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    exam = await _exam(client, auth_headers, internship)
    await client.post(f"{_INTERN}/{internship['id']}/exams/{exam['id']}/assign", json={"send_invites": False}, headers=auth_headers)
    assert await run_all(db_session) == [[], [], [], []]  # two granted students, each matched exactly once: nothing to review
    # a person added by hand with an e-mail that matches no selected student
    added = await client.post(f"{_EXAMS}/{exam['id']}/attendees/manual", json={"name": "Stranger", "email": "stranger@example.com"}, headers=auth_headers)
    assert added.status_code == 201, added.text
    first = (await run_all(db_session))[0]
    assert [(str(r["exam_id"]), r["attendees_matching_no_selection"], r["attendees_matching_several_selections"]) for r in first] == [(exam["id"], 1, 0)]
    # a student whose access was withdrawn: their link is listed as one that will stop working
    asha = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(people["asha@example.com"][0])))).scalar_one()
    asha.lms_status = LmsStatus.REVOKED
    await db_session.flush()
    second = (await run_all(db_session))[1]
    assert [(str(r["exam_id"]), r["lms_status"], r["attendees"]) for r in second] == [(exam["id"], "revoked", 1)]
    assert (await run_all(db_session))[2:] == [[], []]
