"""
The read-only release scripts of ops/release-0107 (00 preflight, 04 post-deployment verification), run for real against a scratch PostgreSQL
database migrated to 0107 by alembic. Docker, AWS and systemd are replaced by small stubs on PATH that forward `psql` to the scratch database
and log every call, so the tests can also prove which docker commands the scripts used (reads only).

What is proved here:
  * the rollback ledger (ops_0107_rollback_hold) does not exist on a first deployment: that is zero active holds, not an error; an existing ledger
    with no open hold passes; an open hold is detected and fails the verification;
  * a query that cannot run (database unreachable, a missing table, a column the SQL needs that is gone) is a FAIL with a clear NO-GO and a nonzero
    exit status, never an empty or successful result; warnings stay warnings (exit status 0, counted apart from FAIL);
  * the scripts do not write: the database counters are unchanged and the only docker commands they use are exec / inspect / logs.

They need `psql` and a reachable PostgreSQL (DATABASE_URL, as for every other database test); they are skipped otherwise.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "ops" / "release-0107"
PREFLIGHT = PACK / "00_preflight_readonly.sh"
VERIFY = PACK / "04_post_deploy_verify.sh"
HOLD_SQL = PACK / "sql" / "rollback_hold.sql"

# PSQL_BIN lets a workstation without a psql client point at a wrapper (e.g. "bash /path/to/psql-shim"); CI has the real client on PATH.
PSQL = shlex.split(os.environ.get("PSQL_BIN", "")) or ([shutil.which("psql")] if shutil.which("psql") else [])
GIT_BASH = r"C:\Program Files\Git\usr\bin\bash.exe"   # Git's bin\bash.exe rebuilds PATH with /usr/bin first, which would hide the stubs; this one does not
BASH = GIT_BASH if sys.platform == "win32" and Path(GIT_BASH).exists() else shutil.which("bash")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
TODAY_UTC = datetime.now(timezone.utc).date().isoformat()   # the script measures the age of the newest daily folder against 03:30 UTC of its date

pytestmark = [
    pytest.mark.skipif(not (PSQL and BASH and DATABASE_URL), reason="needs bash, psql and DATABASE_URL"),
]

DOCKER_STUB = r"""#!/bin/bash
echo "docker $*" >> "$STUB_LOG"
case "$1" in
  exec)
    shift; envs=()
    while [ $# -gt 0 ]; do case "$1" in -i|-t|-it) shift;; -e) envs+=("$2"); shift 2;; -*) shift;; *) break;; esac; done
    target=$1; shift
    for kv in "${envs[@]}"; do export "$kv"; done
    case "$target" in
      shared_postgres)
        if [ "${STUB_DB_DOWN:-0}" = 1 ]; then echo "Error response from daemon: No such container: shared_postgres" >&2; exit 1; fi
        [ "$1" = psql ] || { echo "stub: only psql runs in shared_postgres" >&2; exit 2; }; shift
        rest=(); while [ $# -gt 0 ]; do case "$1" in -U|-d) shift 2;; *) rest+=("$1"); shift;; esac; done
        exec psql "$STUB_PG_URI" "${rest[@]}";;
      erpx_*)
        all="$*"
        case "$all" in
          *urllib.request*) echo "${STUB_HEALTH:-200}";;
          *svglib*) echo "${STUB_PDF:-reportlab 4.4.3 svglib 2.3.1 svg->pdf bytes 900 ok}";;
          *"alembic heads"*) echo "0107 (head)";;
        esac; exit 0;;
    esac; exit 0;;
  inspect)
    shift; fmt=""; names=()
    while [ $# -gt 0 ]; do case "$1" in -f) fmt=$2; shift 2;; *) names+=("$1"); shift;; esac; done
    for n in "${names[@]}"; do
      case "$fmt" in
        *Config.Image*) echo "  /$n image=erpx:test id=sha256:abc status=running health=healthy";;
        *RestartCount*) echo "/$n restarts=0";;
        *State.Health.Status*State.Status*|*State.Status*) echo "${STUB_CONTAINER_STATE:-running/healthy}";;
        *State.Health.Status*) echo "${STUB_API_HEALTH:-healthy}";;
        *) echo stub;;
      esac
    done; exit 0;;
  logs)
    if [ "${STUB_LOGS_FAIL:-0}" = 1 ]; then echo "Error response from daemon: No such container: ${@: -1}" >&2; exit 1; fi
    printf '%s' "${STUB_LOG_TEXT:-}"; exit 0;;
esac
exit 0
"""

SYSTEMCTL_STUB = """#!/bin/bash
echo "systemctl $*" >> "$STUB_LOG"
[ "$1" = is-active ] && echo "${STUB_TIMER:-active}"
exit 0
"""

AWS_STUB = """#!/bin/bash
echo "aws $*" >> "$STUB_LOG"
[ "${STUB_AWS_FAIL:-0}" = 1 ] && { echo "Unable to locate credentials" >&2; exit 255; }
case "$*" in
  *"/daily/"[0-9]*) for f in ${STUB_FILES:-SHA256SUMS manifest.json dump.bin}; do echo "2026-11-22 03:40:00        123 $f"; done;;
  *"/daily/") echo "                           PRE ${STUB_NEWEST}/";;
esac
exit 0
"""

DF_STUB = """#!/bin/bash
case "$*" in
  *--output=avail*) echo "Avail"; echo "${STUB_DF_AVAIL:-60000000000}";;
  *) echo "/dev/stub 100G 40G 60G 40% /";;
esac
"""


def libpq(db: str) -> str:
    parts = urlsplit(DATABASE_URL.replace("postgresql+asyncpg", "postgresql"))
    return urlunsplit((parts.scheme, parts.netloc, "/" + db, "", ""))


def sql(uri: str, statement: str) -> str:
    done = subprocess.run([*PSQL, uri, "-X", "-v", "ON_ERROR_STOP=1", "-tA", "-c", statement], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


@pytest.fixture(scope="module")
def scratch_uri():
    name = "rel0107_" + uuid.uuid4().hex[:8]
    admin = libpq("postgres")
    sql(admin, f'create database "{name}"')
    try:
        asyncpg_url = DATABASE_URL.rsplit("/", 1)[0] + "/" + name
        env = {**os.environ, "DATABASE_URL": asyncpg_url, "PYTHONPATH": str(ROOT)}
        done = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "apps" / "api", env=env, capture_output=True, text=True, timeout=900)
        assert done.returncode == 0, done.stderr[-2000:]
        assert sql(libpq(name), "select version_num from alembic_version") == "0107"
        yield libpq(name)
    finally:
        sql(admin, f'drop database if exists "{name}" with (force)')


@contextmanager
def changed(uri: str, apply: str, revert: str):
    """Change the scratch database for one test and always put it back."""
    sql(uri, apply)
    try:
        yield
    finally:
        sql(uri, revert)


@pytest.fixture()
def world(tmp_path, scratch_uri):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("docker", DOCKER_STUB), ("systemctl", SYSTEMCTL_STUB), ("aws", AWS_STUB), ("df", DF_STUB)):
        path = bin_dir / name
        path.write_text(body, newline="\n")
        path.chmod(0o755)
    pre = tmp_path / "pre-release"
    pre.mkdir()
    erpx = tmp_path / "erpx"
    erpx.mkdir()
    subprocess.run(["git", "init", "-q", str(erpx)], check=True)
    subprocess.run(["git", "-C", str(erpx), "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    log = tmp_path / "calls.log"
    log.write_text("")
    env = {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "STUB_LOG": str(log),
        "STUB_PG_URI": scratch_uri,
        "STUB_NEWEST": TODAY_UTC,
        "PRE_DIR": str(pre),
        "ERPX_DIR": str(erpx),
    }

    class World:
        pass

    w = World()
    w.uri, w.env, w.pre, w.log = scratch_uri, env, pre, log

    def run(script: Path, **extra):
        e = {**env, **{k: str(v) for k, v in extra.items()}}
        done = subprocess.run([BASH, str(script)], env=e, capture_output=True, text=True, timeout=300)
        return done.returncode, done.stdout + done.stderr

    w.run = run
    w.calls = lambda: [line for line in log.read_text().splitlines() if line]
    return w


def counters(uri: str) -> str:
    return sql(uri, "select coalesce(sum(n_tup_ins + n_tup_upd + n_tup_del), 0) from pg_stat_user_tables")


def summary(out: str) -> dict:
    m = re.search(r"SUMMARY: PASS=(\d+) WARN=(\d+) FAIL=(\d+)", out)
    assert m, out[-1500:]
    return {"pass": int(m[1]), "warn": int(m[2]), "fail": int(m[3])}


def drop_ledger(uri):
    sql(uri, "drop table if exists ops_0107_rollback_hold")


LEDGER_DDL = (
    "create table ops_0107_rollback_hold (id bigserial primary key, table_name text not null, row_id uuid not null, original_course_id uuid not null,"
    " parking_course_id uuid not null, held_at timestamptz not null default now(), released_at timestamptz)"
)


# ---------------------------------------------------------------- 04: the rollback ledger -----------------------------------------------------

def test_verify_on_a_first_deployment_has_no_ledger_and_that_is_zero_active_holds(world):
    drop_ledger(world.uri)
    rc, out = world.run(VERIFY)
    assert "[PASS] no rollback ledger exists (no rollback was ever run): zero active holds" in out, out
    assert "relation" not in out and "does not exist" not in out
    assert summary(out)["fail"] == 0 and rc == 0, out


def test_verify_with_an_existing_ledger_and_zero_active_holds_passes(world):
    drop_ledger(world.uri)
    sql(world.uri, LEDGER_DDL)
    sql(world.uri, "insert into ops_0107_rollback_hold (table_name,row_id,original_course_id,parking_course_id,released_at) values ('exam_vivas', gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), now())")
    try:
        rc, out = world.run(VERIFY)
    finally:
        drop_ledger(world.uri)
    assert "the rollback ledger exists and no hold is active" in out, out
    assert summary(out)["fail"] == 0 and rc == 0


def test_verify_still_detects_an_active_hold(world):
    drop_ledger(world.uri)
    sql(world.uri, LEDGER_DDL)
    sql(world.uri, "insert into ops_0107_rollback_hold (table_name,row_id,original_course_id,parking_course_id) values ('exam_vivas', gen_random_uuid(), gen_random_uuid(), gen_random_uuid()), ('lms_assessments', gen_random_uuid(), gen_random_uuid(), gen_random_uuid())")
    try:
        rc, out = world.run(VERIFY)
    finally:
        drop_ledger(world.uri)
    assert "[FAIL] 2 record(s) are parked by a rollback hold" in out, out
    assert rc == 1 and "RESULT: NO-GO" in out


def test_the_real_hold_sql_creates_the_ledger_and_verify_reads_it(world):
    """The ledger the verification reads is the one the hold really creates (an empty database: nothing to hold, ledger created and empty)."""
    drop_ledger(world.uri)
    done = subprocess.run([*PSQL, world.uri, "-X", "-v", "ON_ERROR_STOP=1", "-f", str(HOLD_SQL)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    try:
        rc, out = world.run(VERIFY)
    finally:
        drop_ledger(world.uri)
    assert "the rollback ledger exists and no hold is active" in out and rc == 0, out


# ---------------------------------------------------------------- 04: failures are failures ----------------------------------------------------

def test_verify_with_the_database_down_is_a_clear_no_go(world):
    rc, out = world.run(VERIFY, STUB_DB_DOWN=1)
    s = summary(out)
    assert rc == 1 and s["fail"] >= 3 and "RESULT: NO-GO" in out, out
    assert "[PASS] database revision" not in out and "[PASS] no rollback ledger" not in out
    assert "No such container: shared_postgres" in out


def test_verify_with_a_missing_table_is_a_fail_not_an_empty_result(world):
    with changed(world.uri, "alter table lms_assessments rename to lms_assessments_gone", "alter table lms_assessments_gone rename to lms_assessments"):
        rc, out = world.run(VERIFY)
    assert rc == 1 and "RESULT: NO-GO" in out, out
    assert re.search(r"\[FAIL\] internship-scoped records under deleted courses: the query failed .*lms_assessments", out), out
    assert "[PASS] no internship-scoped record sits under a deleted course" not in out


def test_verify_with_sql_the_schema_cannot_run_is_a_fail(world):
    with changed(world.uri, "alter table exam_vivas rename column internship_id to internship_gone", "alter table exam_vivas rename column internship_gone to internship_id"):
        rc, out = world.run(VERIFY)
    assert rc == 1 and re.search(r"\[FAIL\] internship-scoped records under deleted courses: the query failed .*internship_id", out), out


def test_verify_a_baseline_table_that_does_not_exist_is_a_fail(world):
    (world.pre / "baseline-counts-0107.txt").write_text("no_such_table 5\n", newline="\n")
    rc, out = world.run(VERIFY)
    assert rc == 1 and "[FAIL] row count of no_such_table: the query failed" in out, out


def test_verify_a_shrunk_table_fails_and_a_grown_one_passes(world):
    (world.pre / "baseline-counts-0107.txt").write_text("alembic_version 1\nlms_assessments 7\n", newline="\n")
    rc, out = world.run(VERIFY)
    assert "[PASS] alembic_version rows 1 -> 1" in out and "[FAIL] lms_assessments SHRANK: 7 -> 0" in out, out
    assert rc == 1


def test_verify_a_failed_safety_gate_is_a_no_go(world):
    with changed(world.uri, "update alembic_version set version_num = '0106'", "update alembic_version set version_num = '0107'"):
        rc, out = world.run(VERIFY)
    assert rc == 1 and "[FAIL] database revision is '0106', expected 0107" in out and "RESULT: NO-GO" in out


@pytest.mark.parametrize("env,needle", [
    ({"STUB_HEALTH": "500"}, "[FAIL] api health endpoint: 500"),
    ({"STUB_CONTAINER_STATE": "restarting/unhealthy"}, "[FAIL] erpx_api restarting/unhealthy"),
    ({"STUB_LOGS_FAIL": "1"}, "[FAIL] erpx_api: its log could not be read"),
    ({"STUB_PDF": "boom"}, "[FAIL] erpx_api PDF library check failed"),
    ({"STUB_TIMER": "inactive"}, "[FAIL] offsite-backup.timer is not active"),
])
def test_verify_each_failed_gate_gives_no_go_and_a_nonzero_status(world, env, needle):
    rc, out = world.run(VERIFY, **env)
    assert needle in out, out
    assert rc == 1 and "RESULT: NO-GO" in out


def test_verify_warnings_are_not_failures(world):
    """No baseline file is a genuine warning: it is listed and counted as a warning, and the exit status stays 0."""
    drop_ledger(world.uri)
    rc, out = world.run(VERIFY)
    s = summary(out)
    assert "[WARN] no baseline file" in out
    assert s["warn"] >= 1 and s["fail"] == 0 and rc == 0
    assert "RESULT: automatic checks pass" in out


def test_verify_log_text_with_payment_errors_is_a_fail(world):
    rc, out = world.run(VERIFY, STUB_LOG_TEXT="cashfree webhook failed: invalid signature")
    assert "payment/webhook failure" in out and rc == 1


# ---------------------------------------------------------------- 00: the preflight ----------------------------------------------------------

@contextmanager
def at_revision(uri, rev):
    with changed(uri, f"update alembic_version set version_num = '{rev}'", "update alembic_version set version_num = '0107'"):
        yield


def test_preflight_on_a_database_ready_for_the_release_passes(world):
    with at_revision(world.uri, "0106"):
        drop_ledger(world.uri)
        rc, out = world.run(PREFLIGHT)
    s = summary(out)
    assert rc == 0 and s["fail"] == 0, out
    assert "[PASS] at 0106: the release applies 0107" in out
    assert "[PASS] newest off-server backup is" in out and "[PASS] SHA256SUMS present" in out
    assert "RESULT: no blocker found" in out


def test_preflight_at_0107_with_no_ledger_is_zero_holds(world):
    drop_ledger(world.uri)
    rc, out = world.run(PREFLIGHT)
    assert "[PASS] no rollback ledger exists: zero active holds" in out and "[WARN] already at 0107" in out, out
    assert rc == 0 and summary(out)["fail"] == 0


def test_preflight_refuses_while_a_rollback_hold_is_still_active(world):
    drop_ledger(world.uri)
    sql(world.uri, LEDGER_DDL)
    sql(world.uri, "insert into ops_0107_rollback_hold (table_name,row_id,original_course_id,parking_course_id) values ('exam_vivas', gen_random_uuid(), gen_random_uuid(), gen_random_uuid())")
    try:
        rc, out = world.run(PREFLIGHT)
    finally:
        drop_ledger(world.uri)
    assert "[FAIL] 1 record(s) are held by a previous rollback" in out and rc == 1 and "RESULT: NO-GO" in out


def test_preflight_with_the_database_down_is_a_clear_no_go(world):
    rc, out = world.run(PREFLIGHT, STUB_DB_DOWN=1)
    assert rc == 1 and summary(out)["fail"] >= 6 and "RESULT: NO-GO" in out, out
    for must_not_pass in ("[PASS] no transaction open", "[PASS] nothing waiting for a lock", "[PASS] no exam or quiz attempt", "[PASS] free disk", "RESULT: no blocker"):
        assert must_not_pass not in out, must_not_pass


@pytest.mark.parametrize("rename,label", [
    ("workshop_exam_attendees", "exams in progress"),
    ("lms_assessment_attempts", "exams in progress"),
])
def test_preflight_a_missing_table_is_a_fail(world, rename, label):
    with changed(world.uri, f"alter table {rename} rename to {rename}_gone", f"alter table {rename}_gone rename to {rename}"):
        rc, out = world.run(PREFLIGHT)
    assert rc == 1 and "RESULT: NO-GO" in out
    assert f"[FAIL] {label}: the query failed" in out, out
    assert "[PASS] no exam or quiz attempt is in progress" not in out
    assert "[FAIL] row counts: the query failed" in out


def test_preflight_invalid_sql_in_a_data_report_is_a_fail(world):
    with changed(world.uri, "alter table our_internship_selections rename column lms_status to lms_status_gone", "alter table our_internship_selections rename column lms_status_gone to lms_status"):
        rc, out = world.run(PREFLIGHT)
    assert rc == 1 and "[FAIL] report F (0104-0106): the query failed" in out, out


def test_preflight_a_revision_ahead_of_the_release_is_a_failed_gate(world):
    with at_revision(world.uri, "0108"):
        rc, out = world.run(PREFLIGHT)
    assert rc == 1 and "[FAIL] the database is at 0108, AHEAD of this release" in out


def test_preflight_a_revision_that_is_not_a_revision_is_a_fail(world):
    with at_revision(world.uri, "abc"):
        rc, out = world.run(PREFLIGHT)
    assert rc == 1 and "[FAIL] alembic_version holds 'abc'" in out


@pytest.mark.parametrize("env,needle", [
    ({"STUB_DF_AVAIL": "1000000"}, "[FAIL] free disk"),
    ({"STUB_AWS_FAIL": "1"}, "[FAIL] could not list s3://"),
    ({"STUB_NEWEST": (datetime.now(timezone.utc).date() - timedelta(days=9)).isoformat()}, "[FAIL] newest off-server backup is"),
    ({"STUB_FILES": "dump.bin"}, "[FAIL] SHA256SUMS missing"),
    ({"STUB_TIMER": "inactive"}, "[FAIL] offsite-backup.timer is not active"),
    ({"STUB_API_HEALTH": "unhealthy"}, "[FAIL] erpx_api is not healthy before the release"),
    ({"STUB_NEWEST": "not-a-date"}, "[FAIL] the newest folder under daily/ is named"),
])
def test_preflight_each_failed_gate_is_a_no_go_with_a_nonzero_status(world, env, needle):
    with at_revision(world.uri, "0106"):
        rc, out = world.run(PREFLIGHT, **env)
    assert needle in out, out
    assert rc == 1 and "RESULT: NO-GO" in out


def test_preflight_a_checkout_with_local_changes_is_a_failed_gate(world):
    (Path(world.env["ERPX_DIR"]) / "tracked.txt").write_text("a")
    subprocess.run(["git", "-C", world.env["ERPX_DIR"], "add", "tracked.txt"], check=True)
    with at_revision(world.uri, "0106"):
        rc, out = world.run(PREFLIGHT)
    assert "[FAIL] /opt/erpx has tracked local changes" in out and rc == 1


def test_preflight_warnings_are_not_failures(world):
    """A database below 0104 is a genuine WARNING (more migrations would ship): it is listed and counted apart, and the status stays 0."""
    with at_revision(world.uri, "0103"):
        rc, out = world.run(PREFLIGHT)
    s = summary(out)
    assert "[WARN] at 0103, BELOW 0104" in out and s["warn"] >= 1 and s["fail"] == 0 and rc == 0, out


def test_preflight_dry_run_runs_nothing(world):
    rc, out = world.run(PREFLIGHT, DRY_RUN=1)
    assert rc == 0 and "DRY RUN" in out and world.calls() == []


# ---------------------------------------------------------------- both: read-only guarantees --------------------------------------------------

@pytest.mark.parametrize("script", [PREFLIGHT, VERIFY], ids=["00", "04"])
def test_the_scripts_leave_the_database_and_the_containers_untouched(world, script):
    before = counters(world.uri)
    world.run(script)
    assert counters(world.uri) == before
    verbs = {c.split()[1] for c in world.calls() if c.startswith("docker ")}
    assert verbs <= {"exec", "inspect", "logs"}, f"only read commands may reach docker, saw {verbs}"
    for call in world.calls():
        if call.startswith("docker exec"):
            assert re.search(r"shared_postgres psql|erpx_\w+ python -B -c|erpx_api alembic heads", call), call
        elif call.startswith("aws"):
            assert call.startswith("aws s3 ls "), call
        elif call.startswith("systemctl"):
            assert call.split()[1] in {"is-active", "list-timers"}, call


@pytest.mark.parametrize("script", [PREFLIGHT, VERIFY], ids=["00", "04"])
def test_the_session_options_make_every_kind_of_write_fail(world, script):
    opts = re.search(r'RO_OPTS="([^"]+)"', script.read_text()).group(1)
    env = {**world.env, "PGOPTIONS": opts}
    attempts = [
        "create table zz_probe(i int)", "create temp table zz_probe(i int)", "insert into alembic_version values ('x')", "update alembic_version set version_num = 'x'",
        "delete from alembic_version", "truncate alembic_version", "alter table alembic_version add column z int", "drop table alembic_version", "select nextval('zz_seq')",
    ]
    sql(world.uri, "create sequence zz_seq")
    for stmt in attempts:
        done = subprocess.run([*PSQL, world.uri, "-X", "-c", stmt], env=env, capture_output=True, text=True)
        assert done.returncode != 0, stmt
        assert "read-only transaction" in done.stderr, (stmt, done.stderr)
    sql(world.uri, "drop sequence zz_seq")
    assert sql(world.uri, "select version_num from alembic_version") == "0107"
