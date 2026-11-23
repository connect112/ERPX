"""
The rollback guard for the course-results endpoint (ops/release-0107/rollback_guard/results_routes.py).

A code-only rollback puts the previous release's code back, and its results route let any student with the generic "view results" permission read
any other student's marks. The guard replaces that one route file inside the previous api image. Here the guard's own file is mounted on the real app
(real routing, real authentication, real permission checks, a real database) next to the current route, and its behaviour is checked; the same file
is exercised against the actual previous image by the rollback rehearsal (see RELEASE_CHECKLIST_0107.md). Synthetic data only.
"""

import hashlib
import importlib.util
import re
import uuid
from pathlib import Path

import pytest

from app.main import app
from modules.authorization.repository import AuthorizationRepository
from modules.students.repository import StudentRepository
from tests.api.test_course_content_access import a_course, student_with_role
from tests.api.test_email_studio import user_with

pytestmark = pytest.mark.api

PACK = Path(__file__).resolve().parents[2] / "ops" / "release-0107"
GUARD_FILE = PACK / "rollback_guard" / "results_routes.py"
PREFIX = "/api/v1/_rollback_guard_under_test/results"


@pytest.fixture()
def guard():
    """Mount the guard's router on the app for the duration of one test."""
    spec = importlib.util.spec_from_file_location("rollback_results_routes_under_test", GUARD_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = list(app.router.routes)
    app.include_router(module.router, prefix=PREFIX)
    try:
        yield module
    finally:
        app.router.routes[:] = before


def url(student, course):
    return f"{PREFIX}/{student.id}/course/{course.id}"


async def two_students(client, db, organization):
    a, a_headers = await student_with_role(client, db, organization)
    b, b_headers = await student_with_role(client, db, organization)
    course, _, _ = await a_course(db, organization)
    return a, a_headers, b, b_headers, course


async def test_a_student_reads_their_own_results(client, db_session, organization, rbac_seeded, guard):
    a, a_headers, _, _, course = await two_students(client, db_session, organization)
    r = await client.get(url(a, course), headers=a_headers)
    assert r.status_code == 200, r.text
    assert r.json()["student_id"] == str(a.id)


async def test_a_student_cannot_read_another_students_results(client, db_session, organization, rbac_seeded, guard):
    a, _, _, b_headers, course = await two_students(client, db_session, organization)
    r = await client.get(url(a, course), headers=b_headers)
    assert r.status_code == 403, r.text
    assert "overall_score" not in r.text and "components" not in r.text


async def test_the_current_route_and_the_guard_answer_alike(client, db_session, organization, rbac_seeded, guard):
    """The guard keeps the behaviour release 0107 ships (and not only on the happy path): the same caller gets the same status from both."""
    a, a_headers, _, b_headers, course = await two_students(client, db_session, organization)
    for headers in (a_headers, b_headers):
        now = await client.get(f"/api/v1/examinations/results/{a.id}/course/{course.id}", headers=headers)
        guarded = await client.get(url(a, course), headers=headers)
        assert now.status_code == guarded.status_code


async def test_staff_who_grade_or_manage_can_still_read_any_students_results(client, db_session, organization, rbac_seeded, guard):
    a, _, _, _, course = await two_students(client, db_session, organization)
    for staff_permission in sorted(guard.STAFF):
        headers = await user_with(db_session, organization, ["examinations.results.view", staff_permission])
        r = await client.get(url(a, course), headers=headers)
        assert r.status_code == 200, (staff_permission, r.text)


async def test_a_superuser_can_read_any_students_results(client, db_session, organization, auth_headers, rbac_seeded, guard):
    a, _, _, _, course = await two_students(client, db_session, organization)
    r = await client.get(url(a, course), headers=auth_headers)
    assert r.status_code == 200, r.text


async def test_someone_with_only_the_view_permission_and_no_student_record_is_refused(client, db_session, organization, rbac_seeded, guard):
    """Fail closed: the generic permission alone is not enough. A user who is not the student and holds no staff permission gets nothing."""
    a, _, _, _, course = await two_students(client, db_session, organization)
    headers = await user_with(db_session, organization, ["examinations.results.view"])
    r = await client.get(url(a, course), headers=headers)
    assert r.status_code == 403, r.text


async def test_no_login_means_no_results(client, db_session, organization, rbac_seeded, guard):
    a, _, _, _, course = await two_students(client, db_session, organization)
    assert (await client.get(url(a, course))).status_code in (401, 403)


async def test_if_the_student_record_cannot_be_read_nothing_is_returned(client, db_session, organization, rbac_seeded, guard, monkeypatch):
    a, a_headers, _, _, course = await two_students(client, db_session, organization)

    async def broken(self, user_id):
        raise RuntimeError("cannot read the student record")

    monkeypatch.setattr(StudentRepository, "get_by_user_id", broken)
    with pytest.raises(RuntimeError):
        await client.get(url(a, course), headers=a_headers)


async def test_if_the_permissions_cannot_be_read_nothing_is_returned(client, db_session, organization, rbac_seeded, guard, monkeypatch):
    """Reached only for a caller who is not the student, so the permission lookup is the deciding step: it must not default to 'allowed'."""
    a, _, _, b_headers, course = await two_students(client, db_session, organization)
    calls = {"n": 0}
    real = AuthorizationRepository.get_permission_codes_for_user

    async def flaky(self, user_id):
        calls["n"] += 1
        if calls["n"] > 1:   # the first call is the route's own require_permissions check; the second is the guard's
            raise RuntimeError("cannot read the permissions")
        return await real(self, user_id)

    monkeypatch.setattr(AuthorizationRepository, "get_permission_codes_for_user", flaky)
    with pytest.raises(RuntimeError):
        await client.get(url(a, course), headers=b_headers)


def test_the_guard_serves_the_same_path_and_response_as_the_route_it_replaces(guard):
    paths = {(route.path, tuple(sorted(route.methods))) for route in guard.router.routes}
    assert paths == {("/{student_id}/course/{course_id}", ("GET",))}
    assert guard.ROLLBACK_GUARD == "results-0107"


def test_the_guard_uses_only_what_the_previous_image_has():
    """The guard must run on the previous code, so it may import only modules the previous release already had (checked against the file list of
    release 0106's tree: these are the modules the previous results route and its service already imported or sit beside)."""
    source = GUARD_FILE.read_text(encoding="utf8")
    imported = set(re.findall(r"^(?:from|import) ([\w.]+)", source, re.MULTILINE))
    allowed = {
        "uuid", "fastapi", "sqlalchemy.ext.asyncio", "app.core.exceptions", "app.db.session", "modules.authentication.models",
        "modules.authorization.dependencies", "modules.authorization.repository", "modules.examinations.results.schemas",
        "modules.examinations.results.service", "modules.students.repository", "modules.users.dependencies",
    }
    assert imported <= allowed, imported - allowed
    assert "modules.students.actor" not in source and "modules.learning" not in source


def test_the_guard_names_the_file_it_replaces_by_hash():
    assert re.fullmatch(r"[0-9a-f]{64}", re.search(r'REPLACES_SHA256 = "([0-9a-f]{64})"', GUARD_FILE.read_text(encoding="utf8")).group(1))
    assert hashlib.sha256(GUARD_FILE.read_bytes()).hexdigest() != "4a889744d91d824382172a1641cfb1194fcec52a6b045ea59e75c918bd3360c3"
