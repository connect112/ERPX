"""
90_rollback_code_only.sh (release 0107), run for real in bash against a stub `docker` that keeps container state and logs every call in order.

What these tests prove:
  * ORDER: the writers (celery beat, api, celery worker) are stopped, and the database confirms zero application sessions, BEFORE the dump and the hold
    SQL run; the hold SQL runs before any previous image is started. The stub records which containers were running at the moment the hold SQL arrived.
  * FAIL CLOSED: application sessions still open -> the hold is never run; a saved previous image that is not the version the guards were written for ->
    nothing at all is stopped; guards not confirmed in the running api -> the api is stopped again.
  * RESUME: a rollback stopped half-way is completed by running it again; MODE=forward stops the writers before it releases the hold.
  * EMBEDDING: the committed script contains byte-for-byte sql/*.sql and both rollback_guard files, with the hashes it checks, and it is exactly what the
    generator (wip/build_90_v2.py) produces from the template.
No production anything: no network, no real docker, no database. The guards are exercised in-process in tests/api/test_rollback_{results,progress}_guard.py and over real HTTP
against the real previous image in tests/unit/test_rollback_real_image.py.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "ops" / "release-0107"
SCRIPT = PACK / "90_rollback_code_only.sh"
GUARDS = PACK / "rollback_guard"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(not BASH, reason="needs bash")


def lf(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


RESULTS_GUARD = hashlib.sha256(lf(GUARDS / "results_routes.py")).hexdigest()
PROGRESS_GUARD = hashlib.sha256(lf(GUARDS / "progress_routes.py")).hexdigest()
RESULTS_PREV = re.search(rb'REPLACES_SHA256 = "([0-9a-f]{64})"', lf(GUARDS / "results_routes.py")).group(1).decode()
PROGRESS_PREV = re.search(rb'REPLACES_SHA256 = "([0-9a-f]{64})"', lf(GUARDS / "progress_routes.py")).group(1).decode()

# A stateful stand-in for docker (and for psql / pg_dump inside shared_postgres). State lives in $STUB_STATE; every call is appended to $STUB_LOG.
DOCKER_STUB = r'''#!__PYTHON__
import json, os, sys
state_dir = os.environ["STUB_STATE"]; log = os.environ["STUB_LOG"]
args = sys.argv[1:]
RESULTS_GUARD, PROGRESS_GUARD = os.environ["RESULTS_GUARD"], os.environ["PROGRESS_GUARD"]
RESULTS_PREV, PROGRESS_PREV = os.environ["RESULTS_PREV"], os.environ["PROGRESS_PREV"]
PROGRESS_PATH = "/app/modules/lms/progress/routes.py"

def note(text):
    with open(log, "a") as f: f.write(text + "\n")

def load():
    with open(os.path.join(state_dir, "state.json")) as f: return json.load(f)
def save(s):
    with open(os.path.join(state_dir, "state.json"), "w") as f: json.dump(s, f)
s = load()
def running_now(): return ",".join(f"{n.replace('erpx_', '')}={int(c['running'])}" for n, c in sorted(s["containers"].items()))
def image_guarded(image): return image == "sha256:guarded"

note("docker " + " ".join(args))
cmd = args[0] if args else ""

def out(text="", code=0):
    if text: print(text)
    sys.exit(code)

if cmd == "info": out("ok")
if cmd == "inspect":
    fmt = args[args.index("-f") + 1] if "-f" in args else ""
    name = args[-1]
    c = s["containers"].get(name)
    if c is None: sys.exit(1)
    if "State.Running" in fmt: out("true" if c["running"] else "false")
    if "State.ExitCode" in fmt: out("0")
    if "State.Health.Status" in fmt: out("healthy" if c["running"] else "none")
    if "results-guard" in fmt: out("0107" if image_guarded(c["image"]) else "<no value>")
    if "{{.Image}}" in fmt: out(c["image"])
    out("stub")
if cmd == "image":
    if args[1] == "inspect" and "{{.Id}}" in args: out("sha256:guarded")
    out("ok")
if cmd == "tag":
    s["images"][args[2]] = args[1]; save(s); out()
if cmd == "build":
    s["built"] = True; save(s); out("sha256:guarded")
if cmd == "run":   # sha256 of a route file inside an image (throw-away container)
    image, path = args[-2], args[-1]
    guarded = image_guarded(image)
    if s.get("wrong_previous") and not guarded: out("0" * 64 + "  " + path)
    if path == PROGRESS_PATH: out((PROGRESS_GUARD if guarded else PROGRESS_PREV) + "  " + path)
    out((RESULTS_GUARD if guarded else RESULTS_PREV) + "  " + path)
if cmd == "stop":
    name = args[-1]
    if s.get("stop_fails"): sys.exit(1)
    if name in s["containers"]: s["containers"][name]["running"] = False
    save(s); out(name)
if cmd == "compose":
    if "up" in args:
        svc = args[-1]
        if s.get("compose_fails") and svc == "api" and not s.get("compose_failed_once"):
            s["compose_failed_once"] = True; save(s); print("stub: compose up failed", file=sys.stderr); sys.exit(1)
        s["containers"]["erpx_" + svc] = {"running": True, "image": s["images"].get(f"erpx-{svc}:latest", "sha256:old-" + svc)}
        if svc == "api": s["api_started"] = True
        note(f"START {svc} (running before: {running_now()})")
        save(s)
    if "ps" in args: out("erpx_api  Up")
    out()
if cmd == "exec":
    rest = args[1:]
    while rest and rest[0].startswith("-"):
        rest = rest[2:] if rest[0] == "-e" else rest[1:]
    target, tail = rest[0], rest[1:]
    stdin = "" if sys.stdin.isatty() else sys.stdin.read()
    if target == "shared_postgres":
        if tail[0] == "pg_dump":
            note("PG_DUMP (running: %s)" % running_now()); sys.stdout.buffer.write(b"PGDMP-stub"); sys.exit(0)
        if tail[0] == "pg_restore": print("\n".join("; entry %d" % i for i in range(30))); sys.exit(0)
        sql = tail[tail.index("-c") + 1] if "-c" in tail else stdin
        if "ROLLBACK HOLD 0107" in sql or "released_at = now()" in sql:
            kind = "HOLD-SQL" if "ROLLBACK HOLD 0107" in sql else "RELEASE-SQL"
            note(f"{kind} (running: {running_now()})")
            save(s); print("COMMIT"); sys.exit(0)
        if "pg_stat_activity" in sql and "count(*)" in sql:
            n = s.get("sessions", 0)
            if s.get("sessions_drop_after_stop") and not any(c["running"] for k, c in s["containers"].items() if k in ("erpx_api", "erpx_celery_worker", "erpx_celery_beat")): n = 0
            note(f"SESSIONS-QUERY -> {n} (running: {running_now()})")
            print(n); sys.exit(0)
        if "version_num" in sql: out("0107")
        if "to_regclass" in sql: out("ops_0107_rollback_hold")
        if "rollback-hold-0107" in sql: out("0")
        if "ops_0107_rollback_hold where released_at is null" in sql and "table_name" not in sql: out("0")
        if "ops_0107_rollback_hold where table_name" in sql: out("2")
        if "count(*) from lms_assessments) ||" in sql: out("2|2|2|2")
        if "deleted_at is null" in sql: out(str(s.get("private_visible", 0) if not s.get("late_private") else (s["late_private"] if s.get("api_started") else 0)))
        if "internship_id is not null" in sql: out("2")
        out("0" if "count(*)" in sql else "")
    if target in ("erpx_api", "erpx_celery_worker"):
        joined = " ".join(tail)
        if target == "erpx_celery_worker": out("0" if "lrange" in joined else "")
        guarded = image_guarded(s["containers"][target]["image"]) and not s.get("guard_not_confirmed")
        if tail[0] == "sha256sum":
            path = tail[1]
            out(((PROGRESS_GUARD if path == PROGRESS_PATH else RESULTS_GUARD) if guarded else "bad") + "  " + path)
        if "urllib.request" in joined: out("200")
        if "ROLLBACK_GUARD" in joined: out("GUARDED" if guarded else "NOT-GUARDED")
    out()
out()
'''

DF_STUB = "#!/bin/bash\necho Avail; echo 60000000000\n"
SLEEP_STUB = "#!/bin/bash\nexit 0\n"
SHA_STUB = '#!/bin/bash\nexec shasum -a 256 "$@"\n'


@pytest.fixture()
def host(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stubs = [("docker", DOCKER_STUB.replace("__PYTHON__", sys.executable)), ("df", DF_STUB), ("sleep", SLEEP_STUB)]
    if not shutil.which("sha256sum"):
        stubs.append(("sha256sum", SHA_STUB))
    for name, body in stubs:
        path = bin_dir / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    pre, erpx, state = tmp_path / "pre", tmp_path / "erpx", tmp_path / "state"
    for d in (pre, erpx, state):
        d.mkdir()
    (erpx / "docker-compose.prod.yml").write_text("services: {}\n")
    services = ["api", "celery_worker", "celery_beat", "web", "student_portal", "trainer_portal"]
    lines = []
    for svc in services:
        lines += [f"{svc}_NAME=erpx-{svc}:latest", f"{svc}_OLD_ID=sha256:old-{svc}"]
    (pre / "images-0107.env").write_text("\n".join(lines) + "\n")
    containers = {f"erpx_{svc}": {"running": True, "image": f"sha256:new-{svc}"} for svc in services}
    (state / "state.json").write_text(json.dumps({"containers": containers, "images": {}}))
    log = tmp_path / "calls.log"
    log.write_text("")
    env = {
        **os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "STUB_STATE": str(state), "STUB_LOG": str(log),
        "PRE_DIR": str(pre), "ERPX_DIR": str(erpx), "RESULTS_GUARD": RESULTS_GUARD, "PROGRESS_GUARD": PROGRESS_GUARD,
        "RESULTS_PREV": RESULTS_PREV, "PROGRESS_PREV": PROGRESS_PREV, "API_GRACE": "1", "WORKER_DRAIN": "5", "WORKER_GRACE": "1",
    }

    class Host:
        pass

    h = Host()
    h.pre, h.log, h.state = pre, log, state

    def run(mode="full", script=SCRIPT, **extra):
        e = {**env, "MODE": mode, **{k: str(v) for k, v in extra.items()}}
        done = subprocess.run([BASH, str(script)], env=e, capture_output=True, text=True, timeout=120)
        return done.returncode, done.stdout + done.stderr

    def set_state(**kw):
        s = json.loads((state / "state.json").read_text())
        s.update(kw)
        (state / "state.json").write_text(json.dumps(s))

    h.run, h.set_state = run, set_state
    h.calls = lambda: log.read_text().splitlines()
    h.index = lambda prefix, start=0: next((i for i, c in enumerate(h.calls()) if i >= start and c.startswith(prefix)), None)
    return h


def writers_stopped(line: str) -> bool:
    return all(f"{w}=0" in line for w in ("api", "celery_beat", "celery_worker"))


# ---------------------------------------------------------------- order ---------------------------------------------------------------------

def test_the_writers_are_stopped_and_idle_before_anything_is_modified(host):
    rc, out = host.run("full")
    assert rc == 0, out
    calls = host.calls()
    i_beat, i_api = host.index("docker stop -t 30 erpx_celery_beat"), host.index("docker stop -t 1 erpx_api")
    i_worker = host.index("docker stop -t 1 erpx_celery_worker")
    i_sessions, i_dump, i_hold = host.index("SESSIONS-QUERY"), host.index("PG_DUMP"), host.index("HOLD-SQL")
    i_start = host.index("START ")
    assert None not in (i_beat, i_api, i_worker, i_sessions, i_dump, i_hold, i_start), calls
    assert i_beat < i_api < i_worker < i_sessions < i_dump < i_hold < i_start, calls
    # at the very moment the dump and the hold SQL reached the database, none of the three writers was running
    assert writers_stopped(calls[i_dump]) and writers_stopped(calls[i_hold]), (calls[i_dump], calls[i_hold])
    assert "RESULT: the rolled-back state is confirmed" in out


def test_the_hold_never_runs_while_the_application_still_has_database_sessions(host):
    host.set_state(sessions=3)
    rc, out = host.run("full")
    assert rc == 5, out
    assert "session(s) of 'erpx' are still open" in out and "The hold was NOT run" in out
    assert host.index("HOLD-SQL") is None and host.index("PG_DUMP") is None and host.index("START ") is None, host.calls()


def test_a_previous_image_the_guards_were_not_written_for_changes_nothing(host):
    host.set_state(wrong_previous=True)
    rc, out = host.run("full")
    assert rc == 2 and "NOTHING was changed" in out, out
    assert not any(c.startswith(("docker stop", "HOLD-SQL", "PG_DUMP", "START")) for c in host.calls()), host.calls()
    assert not (host.pre / "rollback-api-override.yml").exists()


def test_guards_not_confirmed_in_the_running_api_stops_it_again_and_fails_closed(host):
    host.set_state(guard_not_confirmed=True)
    rc, out = host.run("full")
    assert rc == 7 and "FAIL CLOSED" in out, out
    calls = host.calls()
    start_api = host.index("START api")
    assert start_api is not None and host.index("docker stop -t 1 erpx_api", start_api) is not None, calls
    assert host.index("START celery_worker") is None and host.index("START celery_beat") is None, calls   # nothing else was started


def test_dry_run_changes_nothing(host):
    rc, out = host.run("full", DRY_RUN=1)
    assert rc == 0, out
    assert not any(c.startswith(("docker stop", "docker build", "docker tag", "HOLD-SQL", "PG_DUMP", "START")) for c in host.calls()), host.calls()
    assert "+ docker stop" in out and "+ psql < rollback_hold.sql" in out
    assert not (host.pre / "rollback-api-override.yml").exists() and not (host.pre / "rollback-0107.state").exists()


# ---------------------------------------------------------------- resume / forward ---------------------------------------------------------

def test_an_interrupted_rollback_is_completed_by_running_it_again(host):
    host.set_state(compose_fails=True)
    rc, out = host.run("full")
    assert rc != 0 and "STOPPED in phase 'images'" in out, out
    assert host.index("HOLD-SQL") is not None
    rc2, out2 = host.run("full")
    assert rc2 == 0 and "RESULT: the rolled-back state is confirmed" in out2, out2


def test_resuming_with_the_previous_api_running_over_visible_private_records_stops_the_api(host):
    """Fail closed: the guarded previous api is up but internship-private records are visible (a half-finished or undone hold)."""
    host.set_state(private_visible=3)
    containers = json.loads((host.state / "state.json").read_text())["containers"]
    containers["erpx_api"] = {"running": True, "image": "sha256:guarded"}
    host.set_state(containers=containers)
    rc, out = host.run("full")
    assert rc == 8 and "STOPPING IT NOW" in out, out
    calls = host.calls()
    assert host.index("docker stop -t 1 erpx_api") is not None, calls          # it really was stopped, not just announced
    assert json.loads((host.state / "state.json").read_text())["containers"]["erpx_api"]["running"] is False
    assert host.index("HOLD-SQL") is None and host.index("START ") is None, calls   # and nothing else happened


def test_if_the_api_cannot_be_stopped_the_failure_says_so_loudly(host):
    host.set_state(private_visible=3, stop_fails=True)
    containers = json.loads((host.state / "state.json").read_text())["containers"]
    containers["erpx_api"] = {"running": True, "image": "sha256:guarded"}
    host.set_state(containers=containers)
    rc, out = host.run("full")
    assert rc == 9 and "STILL RUNNING" in out, out


def test_a_record_that_becomes_visible_after_the_hold_stops_the_freshly_started_api(host):
    """A writer outside the script slipped a private record in after the hold: the api that was just started is stopped again."""
    host.set_state(late_private=1)
    rc, out = host.run("full")
    assert rc == 8 and "STOPPING THE API" in out, out
    calls = host.calls()
    assert host.index("docker stop -t 1 erpx_api", host.index("START api")) is not None, calls
    assert host.index("START celery_worker") is None, calls


def test_roll_forward_stops_the_writers_before_it_releases_the_hold(host):
    assert host.run("full")[0] == 0
    marker = len(host.calls())
    rc, out = host.run("forward")
    assert rc == 0 and "the 0107 code is live again" in out, out
    calls = host.calls()
    i_stop = host.index("docker stop -t 1 erpx_api", marker)
    i_release = host.index("RELEASE-SQL", marker)
    i_start = host.index("START ", marker)
    assert None not in (i_stop, i_release, i_start) and i_stop < i_release < i_start, calls
    assert writers_stopped(calls[i_release])


def test_release_refuses_while_the_previous_api_is_live(host):
    assert host.run("full")[0] == 0
    rc, out = host.run("release")
    assert rc == 2 and "re-expose private records" in out
    assert host.index("RELEASE-SQL") is None


# ---------------------------------------------------------------- embedding ---------------------------------------------------------------

def test_the_script_embeds_the_sql_and_both_guards_byte_for_byte():
    text = lf(SCRIPT).decode()
    for marker, path in (("SQL_HOLD_EOF", PACK / "sql" / "rollback_hold.sql"), ("SQL_RELEASE_EOF", PACK / "sql" / "rollback_release.sql")):
        body = re.search(rf"<<'{marker}'\n(.*?)\n{marker}\n", text, re.S).group(1)
        assert body == lf(path).decode().rstrip("\n"), path.name
    for marker, path, digest in (("GUARD_PY_EOF", GUARDS / "results_routes.py", RESULTS_GUARD), ("PROGRESS_PY_EOF", GUARDS / "progress_routes.py", PROGRESS_GUARD)):
        body = re.search(rf"<<'{marker}'\n(.*?)\n{marker}\n", text, re.S).group(1)
        assert body == lf(path).decode().rstrip("\n"), path.name
        assert hashlib.sha256((body + "\n").encode()).hexdigest() == digest
    for name, value in (("GUARD_SHA256", RESULTS_GUARD), ("P_GUARD_SHA256", PROGRESS_GUARD), ("REPLACES_SHA256", RESULTS_PREV), ("P_REPLACES_SHA256", PROGRESS_PREV)):
        assert re.search(rf"^{name}={value}\b", text, re.M), name
    assert "@@" not in text


def test_the_committed_script_is_exactly_what_the_generator_produces(tmp_path):
    out = tmp_path / "generated.sh"
    done = subprocess.run([sys.executable, str(PACK / "wip" / "build_90_v2.py"), str(out)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert lf(out) == lf(SCRIPT), "run: python ops/release-0107/wip/build_90_v2.py"


def test_the_guard_files_replace_exactly_the_previous_releases_routes():
    """The recorded hashes are those of the real files at the previous release (3a722a6)."""
    git = shutil.which("git")
    if not git or subprocess.run([git, "-C", str(ROOT), "cat-file", "-e", "3a722a6"], capture_output=True).returncode != 0:
        pytest.skip("commit 3a722a6 is not in this clone")
    for path, want in (("modules/examinations/results/routes.py", RESULTS_PREV), ("modules/lms/progress/routes.py", PROGRESS_PREV)):
        blob = subprocess.run([git, "-C", str(ROOT), "show", f"3a722a6:{path}"], capture_output=True, check=True).stdout
        assert hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest() == want, path
