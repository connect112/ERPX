"""
The LATE-WRITER TRAP in ops/release-0107/sql/rollback_hold.sql, run for real in PostgreSQL (a scratch database migrated to 0107 by alembic).

The staging rehearsal showed that a private record written AFTER the hold (by a 0107 api that was not stopped, or a person with psql) was served by the previous
code to an independent enrolee until the script noticed and stopped the api. The hold now also installs a trigger on the four tables that parks such a row as
it is written, in the same way the hold parked the existing ones. These tests prove, on the real SQL: late inserts and updates are parked and recorded;
course-wide rows and everything else are untouched; the hold is idempotent; the release removes the trap first and puts every row back, and nothing is lost.
Synthetic data only. The previous image's HTTP behaviour over this SQL is in tests/unit/test_rollback_real_image.py.
"""

import subprocess
import uuid

import pytest

from tests.unit.test_release_0107_scripts import HOLD_SQL, PACK, PSQL, scratch_uri, sql  # noqa: F401  (scratch_uri is a fixture)

RELEASE_SQL = PACK / "sql" / "rollback_release.sql"
TABLES = {
    "lms_assessments": "(course_id, title, internship_id) values ('{c}', '{t}', {i})",
    "lms_discussion_threads": "(course_id, title, body, internship_id) values ('{c}', '{t}', 'b', {i})",
    "exam_practicals": "(course_id, title, exam_date, internship_id) values ('{c}', '{t}', '2026-12-15', {i})",
    "exam_vivas": "(course_id, title, exam_date, internship_id) values ('{c}', '{t}', '2026-12-16', {i})",
}

pytestmark = pytest.mark.skipif(not PSQL, reason="needs psql")


def run_file(uri, path):
    done = subprocess.run([*PSQL, uri, "-X", "-v", "ON_ERROR_STOP=1", "-q", "-f", str(path)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-800:]


@pytest.fixture()
def world(scratch_uri):
    org = sql(scratch_uri, f"insert into organizations (name, slug) values ('Trap Org', 'trap-{uuid.uuid4().hex[:8]}') returning id").splitlines()[0]
    course = sql(scratch_uri, f"insert into courses (organization_id, title, slug) values ('{org}', 'Trap Course', 'tc-{uuid.uuid4().hex[:8]}') returning id").splitlines()[0]
    other = sql(scratch_uri, f"insert into courses (organization_id, title, slug) values ('{org}', 'Second Course', 'sc-{uuid.uuid4().hex[:8]}') returning id").splitlines()[0]
    internship = sql(scratch_uri, f"insert into our_internships (organization_id, title, scope) values ('{org}', 'Trap Internship', 'all') returning id").splitlines()[0]
    try:
        yield type("W", (), {"uri": scratch_uri, "org": org, "course": course, "other": other, "internship": internship})
    finally:
        for t in TABLES:
            sql(scratch_uri, f"delete from {t} where course_id in (select id from courses where organization_id = '{org}')")
        for t in TABLES:
            sql(scratch_uri, f"drop trigger if exists ops_0107_park_{t} on {t}")
        sql(scratch_uri, "drop function if exists ops_0107_park_private()")
        sql(scratch_uri, "drop table if exists ops_0107_rollback_hold")
        sql(scratch_uri, f"delete from our_internships where id = '{internship}'")
        sql(scratch_uri, f"delete from courses where organization_id = '{org}'")
        sql(scratch_uri, f"delete from organizations where id = '{org}'")


def add(w, table, title, internship=True, course=None):
    values = TABLES[table].format(c=course or w.course, t=title, i=f"'{w.internship}'" if internship else "null")
    return sql(w.uri, f"insert into {table} {values} returning id").splitlines()[0]


def where_is(w, table, row_id):
    return sql(w.uri, f"select c.slug, c.deleted_at is not null from {table} t join courses c on c.id = t.course_id where t.id = '{row_id}'")


def traps(w):
    return int(sql(w.uri, "select count(*) from pg_trigger where tgname like 'ops_0107_park_%' and not tgisinternal"))


def open_ledger(w):
    return int(sql(w.uri, "select count(*) from ops_0107_rollback_hold where released_at is null"))


@pytest.mark.parametrize("table", list(TABLES))
def test_a_private_row_written_after_the_hold_is_parked_as_it_is_written(world, table):
    run_file(world.uri, HOLD_SQL)
    assert traps(world) == 4
    late = add(world, table, "LATE PRIVATE")
    slug, deleted = where_is(world, table, late).split("|")
    assert slug == "rollback-hold-0107" and deleted == "t"
    original = sql(world.uri, f"select original_course_id from ops_0107_rollback_hold where table_name = '{table}' and row_id = '{late}' and released_at is null")
    assert original == world.course   # the ledger remembers where it belongs


@pytest.mark.parametrize("table", list(TABLES))
def test_a_course_wide_row_is_never_touched(world, table):
    run_file(world.uri, HOLD_SQL)
    wide = add(world, table, "COURSEWIDE", internship=False)
    assert sql(world.uri, f"select course_id from {table} where id = '{wide}'") == world.course
    assert open_ledger(world) == 0


def test_moving_a_held_row_to_a_visible_course_parks_it_again_and_keeps_the_original_course(world):
    held = add(world, "lms_assessments", "PRIVATE")
    run_file(world.uri, HOLD_SQL)                                         # moves it
    sql(world.uri, f"update lms_assessments set course_id = '{world.other}' where id = '{held}'")   # somebody tries to un-hide it
    assert where_is(world, "lms_assessments", held).startswith("rollback-hold-0107|")
    assert sql(world.uri, f"select original_course_id from ops_0107_rollback_hold where row_id = '{held}' and released_at is null") == world.course


def test_giving_an_existing_row_an_internship_after_the_hold_parks_it(world):
    wide = add(world, "exam_vivas", "WAS COURSEWIDE", internship=False)
    run_file(world.uri, HOLD_SQL)
    sql(world.uri, f"update exam_vivas set internship_id = '{world.internship}' where id = '{wide}'")
    assert where_is(world, "exam_vivas", wide).startswith("rollback-hold-0107|")


def test_the_hold_is_idempotent_and_loses_nothing(world):
    before = [add(world, t, "P") for t in TABLES]
    run_file(world.uri, HOLD_SQL)
    run_file(world.uri, HOLD_SQL)
    assert traps(world) == 4 and open_ledger(world) == 4
    assert all(where_is(world, t, r).startswith("rollback-hold-0107|") for t, r in zip(TABLES, before))


def test_the_release_removes_the_trap_first_and_puts_every_row_back_including_late_ones(world):
    early = {t: add(world, t, "EARLY") for t in TABLES}
    run_file(world.uri, HOLD_SQL)
    late = {t: add(world, t, "LATE") for t in TABLES}
    assert open_ledger(world) == 8
    run_file(world.uri, RELEASE_SQL)
    assert traps(world) == 0 and open_ledger(world) == 0
    assert int(sql(world.uri, "select count(*) from pg_proc where proname = 'ops_0107_park_private'")) == 0
    for t in TABLES:
        for row in (early[t], late[t]):
            assert sql(world.uri, f"select course_id from {t} where id = '{row}'") == world.course
    # after the release a new private row stays where it is put (the trap is gone)
    fresh = add(world, "lms_assessments", "AFTER RELEASE")
    assert sql(world.uri, f"select course_id from lms_assessments where id = '{fresh}'") == world.course


def test_the_trap_creates_the_holding_course_for_an_organization_that_had_nothing_to_hold(world):
    run_file(world.uri, HOLD_SQL)   # nothing private exists yet: no holding course for this organization
    assert sql(world.uri, f"select count(*) from courses where organization_id = '{world.org}' and slug = 'rollback-hold-0107'") == "0"
    late = add(world, "lms_discussion_threads", "FIRST EVER")
    assert where_is(world, "lms_discussion_threads", late).startswith("rollback-hold-0107|t")
    assert sql(world.uri, f"select is_published from courses where organization_id = '{world.org}' and slug = 'rollback-hold-0107'") == "f"


def test_the_trap_works_for_a_writer_that_has_no_rights_on_the_ledger_or_on_courses(world):
    """In production the late writer is the application role: it can write the four tables but cannot touch ops_0107_rollback_hold or insert courses."""
    role = "trap_writer_" + uuid.uuid4().hex[:6]
    sql(world.uri, f"create role {role}")
    try:
        sql(world.uri, f"grant select, insert, update on lms_assessments, lms_discussion_threads, exam_practicals, exam_vivas to {role}")
        sql(world.uri, f"grant select on courses to {role}")
        run_file(world.uri, HOLD_SQL)
        sql(world.uri, f"grant usage on schema public to {role}")
        # a fresh organization with no holding course yet: the trap must create it too, as definer
        done = subprocess.run([*PSQL, world.uri, "-X", "-q", "-tA", "-v", "ON_ERROR_STOP=1", "-c", f"set role {role}",
                               "-c", f"insert into lms_assessments (course_id, title, internship_id) values ('{world.course}', 'LATE BY APP ROLE', '{world.internship}') returning id"],
                              capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        late = done.stdout.strip().splitlines()[-1]
        assert where_is(world, "lms_assessments", late).startswith("rollback-hold-0107|t")
        assert sql(world.uri, f"select count(*) from ops_0107_rollback_hold where row_id = '{late}' and released_at is null") == "1"
        denied = subprocess.run([*PSQL, world.uri, "-X", "-tA", "-c", f"set role {role}; select count(*) from ops_0107_rollback_hold"], capture_output=True, text=True)
        assert "permission denied" in denied.stderr   # the role still cannot read the ledger itself: only the trap acts on its behalf
    finally:
        sql(world.uri, f"drop owned by {role}")
        sql(world.uri, f"drop role {role}")
