"""
The rollback guard for the LMS course-progress endpoint (ops/release-0107/rollback_guard/progress_routes.py).

The previous release lets any Student (they hold ``lms.progress.view``) read any other student's lesson progress. The rollback bakes this guard into the
previous api image in place of modules/lms/progress/routes.py. Here the guard's router is mounted on the real app (real auth, real permissions, real
database) and checked; tests/unit/test_rollback_real_image.py runs the same file inside the actual previous image over HTTP. Synthetic data only.
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

GUARD_FILE = Path(__file__).resolve().parents[2] / "ops" / "release-0107" / "rollback_guard" / "progress_routes.py"
PREFIX = "/api/v1/_rollback_guard_under_test/progress"


@pytest.fixture()
def guard():
    spec = importlib.util.spec_from_file_location("rollback_progress_routes_under_test", GUARD_FILE)
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


async def test_a_student_reads_their_own_progress(client, db_session, organization, rbac_seeded, guard):
    a, a_headers, _, _, course = await two_students(client, db_session, organization)
    r = await client.get(url(a, course), headers=a_headers)
    assert r.status_code == 200, r.text


async def test_a_student_cannot_read_another_students_progress(client, db_session, organization, rbac_seeded, guard):
    a, _, _, b_headers, course = await two_students(client, db_session, organization)
    r = await client.get(url(a, course), headers=b_headers)
    assert r.status_code == 403, r.text
    assert "completed_lessons" not in r.text and "percentage" not in r.text


async def test_the_unguarded_route_in_this_tree_still_answers_the_other_student(client, db_session, organization, rbac_seeded, guard):
    """Control: the same request on the route as shipped (no guard) succeeds for the other student, so the 403 above is the guard's doing."""
    a, _, _, b_headers, course = await two_students(client, db_session, organization)
    r = await client.get(f"/api/v1/lms/progress/{a.id}/course/{course.id}", headers=b_headers)
    assert r.status_code == 200, r.text


async def test_staff_with_progress_manage_can_read_any_students_progress(client, db_session, organization, rbac_seeded, guard):
    a, _, _, _, course = await two_students(client, db_session, organization)
    headers = await user_with(db_session, organization, ["lms.progress.view", "lms.progress.manage"])
    r = await client.get(url(a, course), headers=headers)
    assert r.status_code == 200, r.text


async def test_a_superuser_can_read_any_students_progress(client, db_session, organization, auth_headers, rbac_seeded, guard):
    a, _, _, _, course = await two_students(client, db_session, organization)
    assert (await client.get(url(a, course), headers=auth_headers)).status_code == 200


async def test_the_view_permission_alone_is_not_enough(client, db_session, organization, rbac_seeded, guard):
    a, _, _, _, course = await two_students(client, db_session, organization)
    headers = await user_with(db_session, organization, ["lms.progress.view"])
    assert (await client.get(url(a, course), headers=headers)).status_code == 403


async def test_no_login_means_no_progress(client, db_session, organization, rbac_seeded, guard):
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
    a, _, _, b_headers, course = await two_students(client, db_session, organization)
    calls = {"n": 0}
    real = AuthorizationRepository.get_permission_codes_for_user

    async def flaky(self, user_id):
        calls["n"] += 1
        if calls["n"] > 1:   # the first call is require_permissions; the second is the guard's
            raise RuntimeError("cannot read the permissions")
        return await real(self, user_id)

    monkeypatch.setattr(AuthorizationRepository, "get_permission_codes_for_user", flaky)
    with pytest.raises(RuntimeError):
        await client.get(url(a, course), headers=b_headers)


async def test_the_guard_keeps_the_previous_releases_other_progress_routes(guard):
    paths = {(route.path, tuple(sorted(route.methods))) for route in guard.router.routes}
    assert paths == {
        ("/me/course/{course_id}", ("GET",)), ("/me/complete/{lesson_id}", ("POST",)), ("/complete", ("POST",)),
        ("/uncomplete", ("POST",)), ("/{student_id}/course/{course_id}", ("GET",)),
    }
    assert guard.ROLLBACK_GUARD == "progress-0107"


def test_the_guard_uses_only_what_the_previous_image_has():
    source = GUARD_FILE.read_text(encoding="utf8")
    imported = set(re.findall(r"^(?:from|import) ([\w.]+)", source, re.MULTILINE))
    allowed = {
        "uuid", "fastapi", "sqlalchemy.ext.asyncio", "app.core.exceptions", "app.db.session", "modules.authentication.models",
        "modules.authorization.dependencies", "modules.authorization.repository", "modules.lms.enrollment.access", "modules.lms.progress.schemas",
        "modules.lms.progress.service", "modules.students.dependencies", "modules.students.models", "modules.students.repository",
        "modules.users.dependencies",
    }
    assert imported <= allowed, imported - allowed
    assert "modules.students.actor" not in source and "modules.learning" not in source


def test_the_guard_names_the_file_it_replaces_by_hash():
    declared = re.search(r'REPLACES_SHA256 = "([0-9a-f]{64})"', GUARD_FILE.read_text(encoding="utf8")).group(1)
    assert declared == "49600eff4e7ca07d0fa34e014b525e7500dfbfdfc97bb3eb9bcac5a03bc16b9b"
    assert hashlib.sha256(GUARD_FILE.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != declared
