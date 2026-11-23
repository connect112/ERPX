"""
The rollback guards, over real HTTP, against the REAL previous-release API image (built from origin/master at 3a722a6).

What happens here (all on this machine, nothing else is touched):
  1. a scratch database is created inside the local PostgreSQL container and filled from the local erpx database (synthetic seed data, schema 0107);
  2. the guarded image is built by the rollback script's own `prepare_guard` function (sourced from 90_rollback_code_only.sh, so the Dockerfile, the hash
     checks and the files baked in are exactly what a real rollback uses) from the previous image;
  3. the previous image WITHOUT the guards and the guarded image each run as a throw-away container (RUN_MIGRATIONS=false, as in a real rollback) against
     the scratch database, and the endpoints are called with real logins.
The control (unguarded previous image) must show the hole: a student reads another student's results and progress. The guarded image must answer 403 to
that, while a student still reads their own, and staff still read anybody's.

Skipped unless Docker, the local stack (erpx_postgres, erpx_api) and the previous image exist. Build the image with:
    git worktree add --detach /tmp/erpx-prev 3a722a6 && docker build -f /tmp/erpx-prev/apps/api/Dockerfile -t erpx-rehearsal/api-prev:3a722a6 /tmp/erpx-prev
(or set ROLLBACK_PREV_IMAGE to any image built from that commit).
"""

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops" / "release-0107" / "90_rollback_code_only.sh"
PREV_IMAGE = os.environ.get("ROLLBACK_PREV_IMAGE", "erpx-rehearsal/api-prev:3a722a6")
PASSWORD = "LearnE2e123!"   # the documented password of the synthetic seed users (scripts/seed_learning_e2e.py)
DOCKER = shutil.which("docker")


def sh(*args, check=True, input=None, timeout=300):
    done = subprocess.run(list(args), capture_output=True, text=True, input=input, timeout=timeout)
    if check and done.returncode != 0:
        raise AssertionError(f"{args[:4]} failed: {done.stderr[-600:]}")
    return done.stdout.strip()


def available() -> str:
    if not DOCKER:
        return "docker is not installed"
    for name in ("erpx_postgres", "erpx_api"):
        if subprocess.run([DOCKER, "inspect", "-f", "{{.State.Running}}", name], capture_output=True, text=True).stdout.strip() != "true":
            return f"{name} is not running (bash scripts/mac-bootstrap.sh up)"
    if subprocess.run([DOCKER, "image", "inspect", PREV_IMAGE], capture_output=True).returncode != 0:
        return f"image {PREV_IMAGE} does not exist"
    return ""


pytestmark = pytest.mark.skipif(bool(available()), reason=available() or "ok")


def psql(db: str, sql: str) -> str:
    return sh(DOCKER, "exec", "-i", "erpx_postgres", "psql", "-U", "erpx", "-d", db, "-X", "-tA", "-v", "ON_ERROR_STOP=1", "-c", sql)


def http(method: str, url: str, token: str | None = None, body: dict | None = None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None)
    req.add_header("content-type", "application/json")
    if token:
        req.add_header("authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


class Api:
    def __init__(self, base):
        self.base = base

    def login(self, email):
        status, body = http("POST", f"{self.base}/api/v1/auth/login", body={"email": email, "password": PASSWORD})
        assert status == 200, f"login {email}: {status}"
        return body["access_token"]

    def get(self, path, token=None):
        return http("GET", self.base + path, token)


@pytest.fixture(scope="module")
def rehearsal(tmp_path_factory):
    suffix = uuid.uuid4().hex[:8]
    db = f"rb_rehearsal_{suffix}"
    tmp = tmp_path_factory.mktemp("rehearsal")
    containers, tags = [], []
    try:
        # 1. scratch database = a copy of the local (synthetic) one
        sh(DOCKER, "exec", "erpx_postgres", "psql", "-U", "erpx", "-d", "postgres", "-qc", f'CREATE DATABASE "{db}"')
        dump = sh(DOCKER, "exec", "erpx_postgres", "pg_dump", "-U", "erpx", "-d", "erpx", "--no-owner")
        sh(DOCKER, "exec", "-i", "erpx_postgres", "psql", "-U", "erpx", "-d", db, "-q", "-X", input=dump, timeout=600)
        assert psql(db, "select version_num from alembic_version") == "0107"
        # 2. the guarded image, built by the rollback script's own function
        funcs = tmp / "funcs.sh"
        text = SCRIPT.read_text()
        funcs.write_text(text[: text.index('case "$MODE" in')])
        pre = tmp / "pre"
        pre.mkdir()
        (pre / "images-0107.env").write_text(f"api_OLD_ID={PREV_IMAGE}\n")
        env = {**os.environ, "MODE": "verify", "PRE_DIR": str(pre), "ERPX_DIR": str(tmp), "GUARD_IMAGE": ""}
        done = subprocess.run(["bash", "-c", f'source "{funcs}"; prepare_guard; echo "GUARD_IMAGE=$GUARD_IMAGE"'], env=env, capture_output=True, text=True, timeout=600)
        assert done.returncode == 0, done.stdout[-800:] + done.stderr[-800:]
        guard_image = re.search(r"^GUARD_IMAGE=(.+)$", done.stdout, re.M).group(1).strip()
        tags += ["erpx-rollback/api:previous-0107", "erpx-rollback/api:guard-0107"]
        # 3. two throw-away previous-release apis on the scratch database
        db_url = sh(DOCKER, "exec", "erpx_api", "printenv", "DATABASE_URL").rsplit("/", 1)[0] + "/" + db
        env_args = []
        for key in ("REDIS_URL", "JWT_SECRET_KEY", "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET"):
            value = sh(DOCKER, "exec", "erpx_api", "printenv", key, check=False)
            if value:
                env_args += ["-e", f"{key}={value}"]
        apis = {}
        for label, image in (("control", PREV_IMAGE), ("guarded", guard_image)):
            name = f"rb_rehearsal_{label}_{suffix}"
            sh(DOCKER, "run", "-d", "--name", name, "--network", "erpx_erpx_network", "-p", "127.0.0.1::8000", "-e", f"DATABASE_URL={db_url}", "-e", "RUN_MIGRATIONS=false",
               "-e", "ENVIRONMENT=test", *env_args, image)
            containers.append(name)
            port = sh(DOCKER, "port", name, "8000/tcp").splitlines()[0].rsplit(":", 1)[1]
            apis[label] = Api(f"http://127.0.0.1:{port}")
        for label, api in apis.items():
            for _ in range(60):
                try:
                    if http("GET", api.base + "/api/v1/health")[0] == 200:
                        break
                except Exception:
                    pass
                time.sleep(2)
            else:
                raise AssertionError(f"{label} api never became healthy: " + sh(DOCKER, "logs", "--tail", "30", f"rb_rehearsal_{label}_{suffix}", check=False))
        ids = {row.split("|")[0]: row.split("|")[1] for row in psql(db, "select split_part(email,'@',1), id from students where email like '%.e2e@example.com'").splitlines()}
        course = psql(db, "select id from courses where deleted_at is null and slug <> 'rollback-hold-0107' and organization_id = (select organization_id from students where email = 'asha.e2e@example.com') order by created_at limit 1")
        yield type("R", (), {"apis": apis, "ids": ids, "course": course, "guard_image": guard_image})
    finally:
        for name in containers:
            subprocess.run([DOCKER, "rm", "-f", name], capture_output=True)
        subprocess.run([DOCKER, "exec", "erpx_postgres", "psql", "-U", "erpx", "-d", "postgres", "-qc", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)'], capture_output=True)
        for tag in tags:
            subprocess.run([DOCKER, "rmi", tag], capture_output=True)


RESULTS = "/api/v1/examinations/results/{s}/course/{c}"
PROGRESS = "/api/v1/lms/progress/{s}/course/{c}"


@pytest.mark.parametrize("template", [RESULTS, PROGRESS], ids=["results", "progress"])
def test_control_the_previous_image_without_the_guards_leaks_between_students(rehearsal, template):
    """Proof the test can see the hole: without the guard, Asha reads Meera's data."""
    api = rehearsal.apis["control"]
    asha = api.login("asha.e2e@example.com")
    status, _ = api.get(template.format(s=rehearsal.ids["meera.e2e"], c=rehearsal.course), asha)
    assert status == 200, status


@pytest.mark.parametrize("template", [RESULTS, PROGRESS], ids=["results", "progress"])
def test_guarded_a_student_cannot_read_another_students_data(rehearsal, template):
    api = rehearsal.apis["guarded"]
    for reader, owner in (("asha.e2e", "meera.e2e"), ("meera.e2e", "asha.e2e"), ("solo.e2e", "asha.e2e")):
        token = api.login(reader + "@example.com")
        status, body = api.get(template.format(s=rehearsal.ids[owner], c=rehearsal.course), token)
        assert status == 403, (reader, owner, status, body)
        assert str(rehearsal.ids[owner]) not in str(body)


@pytest.mark.parametrize("template", [RESULTS, PROGRESS], ids=["results", "progress"])
def test_guarded_a_student_still_reads_their_own(rehearsal, template):
    api = rehearsal.apis["guarded"]
    token = api.login("asha.e2e@example.com")
    status, body = api.get(template.format(s=rehearsal.ids["asha.e2e"], c=rehearsal.course), token)
    assert status == 200, (status, body)


@pytest.mark.parametrize("template", [RESULTS, PROGRESS], ids=["results", "progress"])
def test_guarded_staff_still_read_any_student(rehearsal, template):
    api = rehearsal.apis["guarded"]
    token = api.login("admin.learning.e2e@example.com")
    status, body = api.get(template.format(s=rehearsal.ids["meera.e2e"], c=rehearsal.course), token)
    assert status == 200, (status, body)


@pytest.mark.parametrize("template", [RESULTS, PROGRESS], ids=["results", "progress"])
def test_guarded_no_login_is_refused(rehearsal, template):
    status, _ = rehearsal.apis["guarded"].get(template.format(s=rehearsal.ids["asha.e2e"], c=rehearsal.course))
    assert status in (401, 403)
