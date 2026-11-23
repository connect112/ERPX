#!/bin/bash
# ERPX release 0107 (PR #180)  --  CODE-ONLY ROLLBACK, and the way back (roll-forward).
# The database STAYS at 0107: nothing is downgraded, nothing is deleted, no historical record is touched (student results, submissions, attempts,
# payments and everything else keep their rows; the only column the procedure edits is course_id of internship-private records, and it is put back).
#
# WHAT A PLAIN IMAGE SWAP WOULD DO (proven by rehearsal against the real previous image, not guessed):
#   1. The previous code lists assessments, discussion threads, practicals and vivas by course alone and every student may list them. After a plain swap
#      an independent enrolee sees an internship's private quizzes, threads, practicals and vivas. So those rows are HELD first: moved, unchanged, under a
#      soft-deleted course that the previous code treats as not found. Every move is recorded in ops_0107_rollback_hold; roll-forward puts each row back.
#   2. The previous api refuses to start against a database at 0107 (its entrypoint runs `alembic upgrade head`: "Can't locate revision identified by
#      '0107'"), so it is started with RUN_MIGRATIONS=false through a compose override file in $PRE_DIR.
#   3. The previous code lets ANY student read ANY other student's course results (GET /api/v1/examinations/results/{student_id}/course/{course_id}:
#      it only checks the generic "view results" permission, which every Student holds). Release 0107 fixed that; restoring the old image would bring the
#      hole back. So the previous api image is not restored as it was: a derived image is built FROM it with exactly one file replaced
#      (modules/examinations/results/routes.py -> the guard embedded below: own results, or staff, or superuser; everyone else 403). The build refuses
#      unless the file it replaces is byte-for-byte the previous release's; the running container is checked afterwards, and the api is stopped again
#      if the guard cannot be confirmed (fail closed). The guard lives in the image, so it survives restarts and recreation of the container.
#   4. If the 0107 api keeps writing while the hold runs, a record created in between would be missed. So the writers are stopped first (below).
#   5. A writer that gets in AFTER the hold (a 0107 api somewhere else, a person with psql) would create a private record that the previous code then
#      serves to every enrolee until someone notices (shown in the staging rehearsal). So the hold transaction also installs a database trigger on the four
#      tables that parks such a row as it is written (same holding course, same ledger): prevention, not detection. The release drops it first. Nothing about
#      database roles or connections is changed. The post-start visibility check stays as a second, independent line.
#
# MODES (set MODE on the line below):
#   full      THE ROLLBACK, resumable.  preflight (changes nothing) -> save the 0107 images -> QUIESCE -> HOLD -> restore the previous images -> VERIFY.
#             If anything stops it half-way, run it again with MODE=full: every step checks the real state and continues. To go back to the 0107 code instead, MODE=forward.
#   forward   THE WAY BACK, resumable: stop the writers -> release the hold -> start the saved 0107 images -> verify. Never leaves the previous code live over released records.
#   verify    read-only checks of the rolled-back state (also the answer to "is the protection still in place?"). Exit status 1 if anything fails.
#   release   only the SQL that puts held rows back; refuses unless the 0107 api is the one running (kept for the manual path: steps 01-03, then this).
# DRY_RUN=1 runs only the read-only checks and prints every command that would change something, with a +.
#
# QUIESCE = stop erpx_celery_beat, then erpx_api (docker stop: in-flight requests get $API_GRACE s to finish; a request cut off after that is a database
#   transaction that rolls back, never half a record), then wait for erpx_celery_worker to finish the tasks it is running (up to $WORKER_DRAIN s) and stop it
#   (warm shutdown, up to $WORKER_GRACE s). Tasks still QUEUED in Redis stay queued (nothing is purged); the previous worker consumes them when it starts.
#   It then requires ZERO connections of the application's database user before it writes anything. PostgreSQL, Redis, MinIO, Caddy, the three frontends and
#   every unrelated service keep running. The site shows errors for the few minutes this takes: it is a rollback window.
#
# What it never does: alembic downgrade, drop a table or column, delete a row, restore the pre-release dump, stop or restart PostgreSQL / Redis / MinIO / Caddy,
# touch backups or MinIO files, prune an image.
MODE=${MODE:-PASTE_ONE_OF_full_forward_verify_release}
DRY_RUN=${DRY_RUN:-0}
set -euo pipefail
export LC_ALL=C
PRE_DIR=${PRE_DIR:-/opt/backups/pre-release}; ERPX_DIR=${ERPX_DIR:-/opt/erpx}   # production defaults; only overridden by the rehearsal harness
APP_DB_USER=${APP_DB_USER:-erpx}          # the database user of the application containers (DATABASE_URL in docker-compose.prod.yml)
API_GRACE=${API_GRACE:-60}; WORKER_DRAIN=${WORKER_DRAIN:-180}; WORKER_GRACE=${WORKER_GRACE:-120}

cd "$ERPX_DIR"
COMPOSE="docker compose -f docker-compose.prod.yml"
ENVF=$PRE_DIR/images-0107.env
STATE=$PRE_DIR/rollback-0107.state
OVERRIDE=$PRE_DIR/rollback-api-override.yml
GUARD_DIR=$PRE_DIR/rollback-guard
SERVICES="api celery_worker celery_beat web student_portal trainer_portal"
REPLACES_SHA256=@@REPLACES_SHA256@@       # the previous release's modules/examinations/results/routes.py
GUARD_SHA256=@@GUARD_SHA256@@         # the results guard file embedded below
ROUTES=/app/modules/examinations/results/routes.py
P_REPLACES_SHA256=@@P_REPLACES_SHA256@@   # the previous release's modules/lms/progress/routes.py
P_GUARD_SHA256=@@P_GUARD_SHA256@@     # the progress guard file embedded below
P_ROUTES=/app/modules/lms/progress/routes.py
PHASE=preflight; DONE=0
PASS=0; WARN=0; FAIL=0

run() { if [ "$DRY_RUN" = 1 ]; then echo "+ $*" >&2; else "$@"; fi; }   # the + line goes to stderr so a `> /dev/null` on the call cannot hide it
say() { printf '  [%s] %s\n' "$1" "$2"; case "$1" in PASS) PASS=$((PASS+1));; WARN) WARN=$((WARN+1));; FAIL) FAIL=$((FAIL+1));; esac; }
die() { echo "!! $*"; exit "${2:-1}"; }
q()   { docker exec -i shared_postgres psql -X -U postgres -d erpx -v ON_ERROR_STOP=1 "$@"; }
qro() { docker exec -i -e PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=3000" shared_postgres psql -X -U postgres -d erpx -v ON_ERROR_STOP=1 "$@"; }
# qv SQL: one numeric/text value from a READ-ONLY query; a failed query stops the script (never an empty or zero answer)
qv() { local out; out=$(qro -tA -c "$1") || die "a database query failed: ${1:0:80}"; printf '%s\n' "$out" | tail -1; }
qnum() { local v; v=$(qv "$1"); [[ "$v" =~ ^[0-9]+$ ]] || die "unexpected database answer '${v:0:40}' for: ${1:0:80}"; printf '%s' "$v"; }
# first occurrence wins: the first line is the image that really ran before this release (a re-run of step 01 may later record an already-guarded api)
load() { grep -E "^$1=" "$ENVF" | head -1 | cut -d= -f2- || true; }
sget() { if [ -f "$STATE" ]; then grep -E "^$1=" "$STATE" | tail -1 | cut -d= -f2- || true; fi; }
sset() { if [ "$DRY_RUN" = 1 ]; then echo "+ state: $1=$2"; else printf '%s=%s\n' "$1" "$2" >> "$STATE"; fi; }
container_of() { echo "erpx_$1"; }
ctr_image() { docker inspect -f '{{.Image}}' "$1" 2>/dev/null || true; }
ctr_running() { [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || echo false)" = true ]; }
rev() { qv "select version_num from alembic_version"; }
# Stop the api and CONFIRM it: docker must report State.Running == false. Any other answer (still true, the container cannot be inspected, docker
# unreachable) is "not confirmed", and the script ends with exit 9 (critical: the api may still be serving users). Never reports a safe state on faith.
stop_api_confirmed() { # $1 = why (printed if the stop cannot be confirmed)
  docker stop -t "$API_GRACE" erpx_api > /dev/null 2>&1 || true
  local st; st=$(docker inspect -f '{{.State.Running}}' erpx_api 2>/dev/null || echo unknown)
  [ "$st" = false ] && return 0
  echo "!! CRITICAL: erpx_api is NOT confirmed stopped (docker reports '${st:0:20}'). $1"
  die "the previous api may STILL BE RUNNING and serving users. Stop it by hand (docker stop erpx_api; docker inspect -f '{{.State.Running}}' erpx_api must print false) before anything else. Do not trust any earlier message that said it was stopped." 9
}


on_exit() {
  local rc=$?
  [ "$DONE" = 1 ] && return 0
  [ "$rc" -eq 0 ] && return 0
  echo; echo "!! STOPPED in phase '$PHASE' (exit $rc)."
  if [ "$rc" -eq 9 ]; then
    echo "!! CRITICAL (exit 9): the api could NOT be confirmed stopped. Assume it is RUNNING and serving users until you have stopped it by hand and docker reports State.Running=false."
    return 0
  fi
  case "$PHASE" in
    preflight|record) echo "!! Nothing that serves users was changed. Fix the cause above and run again." ;;
    quiesce|hold|images|start|release)
      echo "!! The api / celery worker / beat may be STOPPED (the site shows errors); PostgreSQL and the frontends are untouched. The database is intact: the hold and the release are each all-or-nothing."
      echo "!! Run this script again with the SAME MODE: it checks the real state and continues. To go the other way: MODE=forward puts the 0107 code back; MODE=full re-does the rollback." ;;
    verify) echo "!! The restore finished but a check failed. See the FAIL lines. The api is running only if the guard was confirmed; run MODE=verify again after fixing, or MODE=forward." ;;
  esac
}
trap on_exit EXIT

# ---------------------------------------------------------------------------------------------------------------------------------------------------
# the guard: Dockerfile + the replacement route file (embedded, identical to ops/release-0107/rollback_guard/results_routes.py; a test keeps them equal)
write_guard_context() {
  mkdir -p "$GUARD_DIR"
  cat > "$GUARD_DIR/routes.py" <<'GUARD_PY_EOF'
@@GUARD_PY@@
GUARD_PY_EOF
  cat > "$GUARD_DIR/progress_routes.py" <<'PROGRESS_PY_EOF'
@@PROGRESS_PY@@
PROGRESS_PY_EOF
  [ "$(sha256sum "$GUARD_DIR/routes.py" | cut -d' ' -f1)" = "$GUARD_SHA256" ] || die "the results guard file was damaged when it was written (hash differs); nothing was built" 2
  [ "$(sha256sum "$GUARD_DIR/progress_routes.py" | cut -d' ' -f1)" = "$P_GUARD_SHA256" ] || die "the progress guard file was damaged when it was written (hash differs); nothing was built" 2
  cat > "$GUARD_DIR/Dockerfile" <<DOCKERFILE_EOF
FROM erpx-rollback/api:previous-0107
LABEL erpx.rollback.results-guard="0107"
COPY --chown=erpx:erpx routes.py $ROUTES
COPY --chown=erpx:erpx progress_routes.py $P_ROUTES
RUN python -B -c "import ast, hashlib; [(ast.parse(b), (hashlib.sha256(b).hexdigest() == h) or exit('guard file differs')) for f, h in (('$ROUTES', '$GUARD_SHA256'), ('$P_ROUTES', '$P_GUARD_SHA256')) for b in [open(f, 'rb').read()]]"
DOCKERFILE_EOF
}

# the routes.py inside an image, by hash (a throw-away container: no network, read-only filesystem; no existing container is touched)
image_routes_sha() { docker run --rm --network none --read-only --entrypoint sha256sum "$1" "${2:-$ROUTES}" 2>/dev/null | cut -d' ' -f1; }

prepare_guard() {
  echo "== GUARD: the results endpoint of the previous release lets any student read any other student's results. Preparing the protected previous api image."
  local base had phad; base=$(load api_OLD_ID)
  [ -n "$base" ] || die "api_OLD_ID is not in $ENVF" 2
  if [ "$DRY_RUN" = 1 ]; then
    echo "+ docker run --rm --network none --read-only --entrypoint sha256sum $base $ROUTES   (must equal $REPLACES_SHA256, or already be the guard $GUARD_SHA256)"
    echo "+ the same for $P_ROUTES   (must equal $P_REPLACES_SHA256, or already be the guard $P_GUARD_SHA256)"
    echo "+ write $GUARD_DIR/{Dockerfile,routes.py}; docker tag $base erpx-rollback/api:previous-0107; docker build -t erpx-rollback/api:guard-0107 $GUARD_DIR"
    GUARD_IMAGE=$base; return 0
  fi
  had=$(image_routes_sha "$base"); phad=$(image_routes_sha "$base" "$P_ROUTES")
  if [ "$had" = "$GUARD_SHA256" ] && [ "$phad" = "$P_GUARD_SHA256" ]; then
    echo "the saved api image already carries the guard (an earlier rollback): using it as it is"
    GUARD_IMAGE=$base
  elif { [ "$had" = "$REPLACES_SHA256" ] || [ "$had" = "$GUARD_SHA256" ]; } && { [ "$phad" = "$P_REPLACES_SHA256" ] || [ "$phad" = "$P_GUARD_SHA256" ]; }; then
    echo "the previous api image has exactly the results and progress routes these guards replace: building the guarded image"
    write_guard_context
    docker tag "$base" erpx-rollback/api:previous-0107
    docker build -q -t erpx-rollback/api:guard-0107 "$GUARD_DIR" > /dev/null
    GUARD_IMAGE=$(docker image inspect -f '{{.Id}}' erpx-rollback/api:guard-0107)
    { [ "$(image_routes_sha "$GUARD_IMAGE")" = "$GUARD_SHA256" ] && [ "$(image_routes_sha "$GUARD_IMAGE" "$P_ROUTES")" = "$P_GUARD_SHA256" ]; } || die "the guarded image was built but its route files are not the guards; nothing was changed" 2
  else
    die "the results route ('${had:-unreadable}') or the progress route ('${phad:-unreadable}') inside the saved previous api image is not the version the guards were written and tested for ($REPLACES_SHA256 / $P_REPLACES_SHA256). The protection cannot be guaranteed, so NOTHING was changed and the previous image will not be restored. Decide with a developer (roll forward / fix forward instead)." 2
  fi
  say PASS "guarded previous api image ready: $GUARD_IMAGE"
}

# the guard in the RUNNING api container, three independent ways. Anything unconfirmed is a FAIL.
check_guard_running() {
  local c=erpx_api label inside code
  label=$(docker inspect -f '{{index .Config.Labels "erpx.rollback.results-guard"}}' $c 2>/dev/null || true)
  [ "$label" = 0107 ] && say PASS "erpx_api runs an image labelled erpx.rollback.results-guard=0107" || say FAIL "erpx_api image has no guard label ('$label')"
  inside=$(docker exec -e PYTHONDONTWRITEBYTECODE=1 $c sha256sum $ROUTES 2>/dev/null | cut -d' ' -f1 || true)
  [ "$inside" = "$GUARD_SHA256" ] && say PASS "the results route file inside the running container is the guard (sha256 matches)" || say FAIL "the results route file inside erpx_api is '${inside:-unreadable}', not the guard"
  code=$(docker exec -e PYTHONDONTWRITEBYTECODE=1 $c python -B -c "
from modules.examinations.results import routes
r = [x for x in routes.router.routes if x.path == '/{student_id}/course/{course_id}']
import inspect
ok = routes.ROLLBACK_GUARD == 'results-0107' and len(r) == 1 and '_ensure_own_or_staff' in inspect.getsource(r[0].endpoint)
print('GUARDED' if ok else 'NOT-GUARDED')" 2>&1 | tail -1 || true)
  [ "$code" = GUARDED ] && say PASS "the route that answers /examinations/results/{student_id}/course/{course_id} in the running api calls the own-or-staff check" || say FAIL "the running api's results route is not confirmed guarded ('${code:0:80}')"
  inside=$(docker exec -e PYTHONDONTWRITEBYTECODE=1 $c sha256sum $P_ROUTES 2>/dev/null | cut -d' ' -f1 || true)
  [ "$inside" = "$P_GUARD_SHA256" ] && say PASS "the progress route file inside the running container is the guard (sha256 matches)" || say FAIL "the progress route file inside erpx_api is '${inside:-unreadable}', not the guard"
  code=$(docker exec -e PYTHONDONTWRITEBYTECODE=1 $c python -B -c "
from modules.lms.progress import routes
import inspect
r = [x for x in routes.router.routes if x.path == '/{student_id}/course/{course_id}']
ok = routes.ROLLBACK_GUARD == 'progress-0107' and len(r) == 1 and '_ensure_own_or_staff' in inspect.getsource(r[0].endpoint)
print('GUARDED' if ok else 'NOT-GUARDED')" 2>&1 | tail -1 || true)
  [ "$code" = GUARDED ] && say PASS "the route that answers /lms/progress/{student_id}/course/{course_id} in the running api calls the own-or-staff check" || say FAIL "the running api's progress route is not confirmed guarded ('${code:0:80}')"
}

# ---------------------------------------------------------------------------------------------------------------------------------------------------
gates() {
  echo "== PREFLIGHT (changes nothing)"
  [ -f docker-compose.prod.yml ] || die "no docker-compose.prod.yml in $ERPX_DIR" 2
  docker info > /dev/null 2>&1 || die "the docker daemon is not reachable" 2
  [ -s "$ENVF" ] || die "$ENVF is missing: step 01 saves the images to roll back to; without it there is nothing safe to restore" 2
  for svc in $SERVICES; do
    [ -n "$(load ${svc}_NAME)" ] && [ -n "$(load ${svc}_OLD_ID)" ] || die "no saved image for $svc in $ENVF" 2
    docker image inspect "$(load ${svc}_OLD_ID)" > /dev/null 2>&1 || die "the saved image of $svc ($(load ${svc}_OLD_ID)) no longer exists on this host" 2
  done
  local avail; avail=$(df -B1 --output=avail / | tail -1 | tr -d ' ')
  [[ "$avail" =~ ^[0-9]+$ ]] && [ "$avail" -ge 1000000000 ] || die "less than 1 GB free (or df failed): not enough room to build the guarded image and the pre-hold dump" 3
  local r; r=$(rev)
  [[ "$r" =~ ^[0-9]{4}$ ]] || die "alembic_version is '$r'" 2
  [ "$((10#$r))" -le 107 ] || die "the database is at $r, AHEAD of 0107: this procedure does not apply" 2
  echo "database revision: $r   previous api image: $(load api_OLD_ID)"
  say PASS "preflight: saved images exist, docker and the database answer, revision $r"
}

record_new_images() {
  PHASE=record
  if [ -n "$(sget NEW_api_ID)" ]; then echo "the 0107 images were saved by an earlier run of this rollback (kept; needed for MODE=forward)"; return 0; fi
  echo "== save the images that run now (the 0107 build) so MODE=forward can put them back"
  local ts; ts=$(date -u +%Y%m%dT%H%M%SZ)
  for svc in $SERVICES; do
    local id; id=$(ctr_image "$(container_of $svc)")
    [ -n "$id" ] || { echo "(no container for $svc: nothing to save)"; continue; }
    run docker tag "$id" "erpx-rollback/$svc:new-0107-$ts"
    sset "NEW_${svc}_ID" "$id"
  done
  sset STARTED_AT "$ts"; sset GUARD_IMAGE "$GUARD_IMAGE"
}

worker_info() {
  echo "  tasks running in the worker now: $({ docker exec erpx_celery_worker sh -c 'celery -A app.core.celery_app inspect active -d celery@$(hostname) -t 5 --json 2>/dev/null' 2>/dev/null | grep -o '"id"' || true; } | wc -l)"
}
worker_active() { { docker exec erpx_celery_worker sh -c 'celery -A app.core.celery_app inspect active -d celery@$(hostname) -t 5 --json 2>/dev/null' 2>/dev/null | grep -o '"id"' || true; } | wc -l | tr -d ' '; }
queue_info() {
  echo "  tasks waiting in the broker queue (names and counts only; they stay queued and are NOT purged):"
  docker exec erpx_celery_worker python -B -c "
import os, json, collections, redis
r = redis.Redis.from_url(os.environ['CELERY_BROKER_URL'])
msgs = r.lrange('celery', 0, 4999)
c = collections.Counter()
for m in msgs:
    try: c[json.loads(m)['headers']['task']] += 1
    except Exception: c['(unreadable)'] += 1
print('   ', len(msgs), dict(c))" 2>&1 | tail -2 || echo "    (could not read the queue)"
}

quiesce() {
  PHASE=quiesce
  echo "== QUIESCE: stopping the writers (api, celery beat, celery worker). PostgreSQL, Redis, MinIO, Caddy, the frontends and all other services keep running."
  if ctr_running erpx_celery_beat; then echo "stopping erpx_celery_beat (no new scheduled tasks)"; run docker stop -t 30 erpx_celery_beat > /dev/null; else echo "erpx_celery_beat is not running"; fi
  if ctr_running erpx_api; then echo "stopping erpx_api (requests in progress get up to ${API_GRACE}s)"; run docker stop -t "$API_GRACE" erpx_api > /dev/null; else echo "erpx_api is not running"; fi
  if ctr_running erpx_celery_worker; then
    worker_info; queue_info
    if [ "$DRY_RUN" = 1 ]; then echo "+ wait up to ${WORKER_DRAIN}s for the running tasks to finish, then docker stop -t $WORKER_GRACE erpx_celery_worker"
    else
      local n=1 i
      for i in $(seq 1 $((WORKER_DRAIN / 5))); do n=$(worker_active); [ "$n" = 0 ] && break; sleep 5; done
      [ "$n" = 0 ] && echo "  the worker has no task in progress" || echo "  !! $n task(s) still running after ${WORKER_DRAIN}s: the worker is told to shut down warmly and gets ${WORKER_GRACE}s more"
      docker stop -t "$WORKER_GRACE" erpx_celery_worker > /dev/null
      [ "$(docker inspect -f '{{.State.ExitCode}}' erpx_celery_worker)" = 0 ] && echo "  the worker stopped cleanly" || echo "  !! the worker was killed after the grace period: a task that was running was cut off (its transaction rolled back; check the task log if a mail or a PDF was in progress)"
    fi
  else echo "erpx_celery_worker is not running"; fi
  if [ "$DRY_RUN" = 1 ]; then echo "+ require 0 database sessions of user $APP_DB_USER (wait up to 60s)"; return 0; fi
  local k=1 i
  for i in $(seq 1 30); do k=$(qnum "select count(*) from pg_stat_activity where datname = current_database() and usename = '$APP_DB_USER' and pid <> pg_backend_pid()"); [ "$k" = 0 ] && break; sleep 2; done
  if [ "$k" != 0 ]; then
    qro -c "select pid, state, now() - xact_start as txn_age, left(query, 70) as query from pg_stat_activity where datname = current_database() and usename = '$APP_DB_USER' and pid <> pg_backend_pid()" || true
    die "$k database session(s) of '$APP_DB_USER' are still open although the application containers are stopped: something else is writing. The hold was NOT run. Find the client (see above) and run again." 5
  fi
  say PASS "no application is connected to the database: nothing can write while the hold runs"
  sset QUIESCED_AT "$(date -u +%Y%m%dT%H%M%SZ)"
}

PRIVATE_VISIBLE_SQL="select (select count(*) from lms_assessments t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is null) + (select count(*) from lms_discussion_threads t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is null) + (select count(*) from exam_practicals t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is null) + (select count(*) from exam_vivas t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is null)"
TRAPS_SQL="select count(*) from pg_trigger where tgname like 'ops_0107_park_%' and not tgisinternal"
COUNTS_SQL="select (select count(*) from lms_assessments) || '|' || (select count(*) from lms_discussion_threads) || '|' || (select count(*) from exam_practicals) || '|' || (select count(*) from exam_vivas)"

hold() {
  PHASE=hold
  local r; r=$(rev)
  if [ "$r" != 0107 ]; then echo "database is at $r, not 0107: the 0107 records do not exist, so there is nothing to hold"; return 0; fi
  local before after ts; before=$(qv "$COUNTS_SQL"); ts=$(date -u +%Y%m%dT%H%M%SZ)
  echo "== HOLD, step 1: safety copy of the tables the hold edits (small, custom format), verified readable before anything is changed"
  if [ "$DRY_RUN" = 1 ]; then echo "+ pg_dump -Fc -t lms_assessments -t lms_discussion_threads -t exam_practicals -t exam_vivas -t courses > $PRE_DIR/pre-hold-$ts.dump (+ pg_restore --list)"
  else
    docker exec shared_postgres pg_dump -U postgres -d erpx -Fc -t lms_assessments -t lms_discussion_threads -t exam_practicals -t exam_vivas -t courses > "$PRE_DIR/pre-hold-$ts.dump.partial"
    [ -s "$PRE_DIR/pre-hold-$ts.dump.partial" ] || die "the safety copy is empty; the hold was NOT run" 6
    [ "$(docker exec -i shared_postgres pg_restore --list < "$PRE_DIR/pre-hold-$ts.dump.partial" | wc -l)" -gt 10 ] || die "the safety copy cannot be read back; the hold was NOT run" 6
    mv "$PRE_DIR/pre-hold-$ts.dump.partial" "$PRE_DIR/pre-hold-$ts.dump"; ls -l "$PRE_DIR/pre-hold-$ts.dump"
  fi
  echo "== HOLD, step 2: move the internship-private records out of reach of the previous code (one transaction, checks its own result)"
  if [ "$DRY_RUN" = 1 ]; then echo "+ psql < rollback_hold.sql (embedded below)"; else q <<'SQL_HOLD_EOF'
@@SQL_HOLD@@
SQL_HOLD_EOF
  fi
  [ "$DRY_RUN" = 1 ] && return 0
  echo "== HOLD, step 3: independent verification"
  after=$(qv "$COUNTS_SQL")
  [ "$before" = "$after" ] && say PASS "no record was lost or added: lms_assessments|threads|practicals|vivas = $after" || die "row counts changed during the hold ($before -> $after)" 6
  [ "$(qnum "$PRIVATE_VISIBLE_SQL")" = 0 ] && say PASS "no internship-private record is reachable through a visible course" || die "internship-private records are still under a visible course" 6
  local t open all
  for t in lms_assessments lms_discussion_threads exam_practicals exam_vivas; do
    all=$(qnum "select count(*) from $t where internship_id is not null"); open=$(qnum "select count(*) from ops_0107_rollback_hold where table_name = '$t' and released_at is null")
    [ "$all" = "$open" ] && say PASS "$t: $all internship-scoped record(s), $open held and recorded in the ledger" || die "$t: $all internship-scoped record(s) but $open in the ledger" 6
  done
  [ "$(qnum "select count(*) from courses where slug = 'rollback-hold-0107' and (deleted_at is null or is_published)")" = 0 ] && say PASS "every holding course is soft-deleted and unpublished" || die "a holding course is visible" 6
  [ "$(qnum "$TRAPS_SQL")" = 4 ] && say PASS "late-writer trap installed on all four tables: a private record written from now on is parked as it is written" || die "the late-writer trap is not installed on all four tables" 6
  sset HELD_AT "$(date -u +%Y%m%dT%H%M%SZ)"
}

wait_api_healthy() {
  local st=none i; echo "== wait for $1 to be healthy (up to 4 minutes)"
  for i in $(seq 1 48); do st=$(docker inspect -f '{{.State.Health.Status}}' erpx_api 2>/dev/null || echo none); [ "$st" = healthy ] && break; sleep 5; done
  echo "api health: $st"
  [ "$st" = healthy ] || { docker logs --tail 40 erpx_api 2>&1 | cut -c1-220; return 1; }
}

restore_images() {
  PHASE=images
  echo "== RESTORE the previous release (api from the GUARDED image; RUN_MIGRATIONS=false; the other five as they were)"
  if [ "$DRY_RUN" != 1 ]; then printf 'services:\n  api:\n    environment:\n      RUN_MIGRATIONS: "false"\n' > "$OVERRIDE"; else echo "+ write $OVERRIDE (api: RUN_MIGRATIONS=false)"; fi
  local svc name target
  for svc in $SERVICES; do
    name=$(load "${svc}_NAME"); target=$(load "${svc}_OLD_ID"); [ "$svc" = api ] && target=$GUARD_IMAGE
    run docker tag "$target" "$name"
    if [ "$svc" = api ]; then run docker compose -f docker-compose.prod.yml -f "$OVERRIDE" up -d --no-deps --no-build api
    else run $COMPOSE up -d --no-deps --no-build "$svc"; fi
    echo "$svc is on $target"
    if [ "$svc" = api ] && [ "$DRY_RUN" != 1 ]; then
      wait_api_healthy "the previous api" || die "the previous api is not healthy. The hold is in place and the database is untouched at $(rev). Run again, or MODE=forward." 4
      PASS=0; WARN=0; FAIL=0; check_guard_running
      if [ "$FAIL" -gt 0 ]; then
        echo "!! FAIL CLOSED: the protection for the results endpoint could not be confirmed, so the api is being stopped again."
        stop_api_confirmed "The guard is not confirmed."
        die "the previous api was stopped because the guard is not confirmed. Nothing else was started. Fix the cause or run MODE=forward." 7
      fi
      # last line of defence against a late writer: if an internship-private record became visible between the hold and now, stop the api again
      if [ "$(qnum "$PRIVATE_VISIBLE_SQL" || echo X)" != 0 ]; then
        echo "!! internship-private records are visible although the hold finished (a writer outside this script?): STOPPING THE API (fail closed)."
        stop_api_confirmed "Private records are visible."
        die "the previous api was stopped (confirmed): private records are visible. Find what wrote to the database (see the checklist, part 4.3), then run MODE=full again." 8
      fi
    fi
  done
  sset RESTORED_AT "$(date -u +%Y%m%dT%H%M%SZ)"; sset GUARD_IMAGE "$GUARD_IMAGE"
}

do_verify() {
  PHASE=verify; PASS=0; WARN=0; FAIL=0
  echo "== VERIFY the rolled-back state (read-only)"
  local r; r=$(rev); echo "  database revision: $r (a code-only rollback leaves it at 0107)"
  local h; h=$(docker exec -e PYTHONDONTWRITEBYTECODE=1 erpx_api python -B -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/api/v1/health').status)" 2>&1 | tail -1 || true)
  [ "$h" = 200 ] && say PASS "api health endpoint answers 200" || say FAIL "api health endpoint: ${h:0:80}"
  local svc c want have
  for svc in $SERVICES; do
    c=$(container_of "$svc"); have=$(ctr_image "$c"); want=$(load "${svc}_OLD_ID"); [ "$svc" = api ] && want=$(sget GUARD_IMAGE)
    [ -n "$want" ] && [ "$want" = "$have" ] && say PASS "$c runs the previous release's image${svc/api/ (guarded)}" || say FAIL "$c runs ${have:-nothing}, expected ${want:-?}"
    ctr_running "$c" && true || say FAIL "$c is not running"
  done
  check_guard_running
  if [ "$r" = 0107 ]; then
    [ "$(qnum "$PRIVATE_VISIBLE_SQL")" = 0 ] && say PASS "no internship-private record is reachable through a visible course" || say FAIL "internship-private records are reachable through a visible course"
    [ "$(qnum "$TRAPS_SQL")" = 4 ] && say PASS "late-writer trap present on all four tables" || say FAIL "late-writer trap is missing or incomplete: a record written now would be visible to enrolees"
    echo "  hold ledger (held_now = records currently hidden):"; qro -c "select table_name, count(*) filter (where released_at is null) as held_now, count(*) as ever_held from ops_0107_rollback_hold group by 1 order by 1" 2>&1 | sed 's/^/    /' || true
  fi
  $COMPOSE ps --format 'table {{.Name}}\t{{.Status}}' | head -20
  echo; echo "== SUMMARY: PASS=$PASS WARN=$WARN FAIL=$FAIL"
  if [ "$FAIL" -gt 0 ]; then echo "RESULT: NO-GO: the rolled-back state is NOT confirmed (see FAIL lines)"; return 1; fi
  echo "RESULT: the rolled-back state is confirmed (previous release live, protected results endpoint, private records held)"
}

# ---------------------------------------------------------------------------------------------------------------------------------------------------
release_sql() {
  PHASE=release
  local r; r=$(rev); [ "$r" = 0107 ] || die "the database is at $r, not 0107; nothing was done" 2
  if [ "$(qv "select coalesce(to_regclass('ops_0107_rollback_hold')::text, '')")" = "" ]; then echo "no rollback ledger exists: nothing was held, nothing to release"; return 0; fi
  echo "== RELEASE: put every held record back under its original course"
  if [ "$DRY_RUN" = 1 ]; then echo "+ psql < rollback_release.sql (embedded below)"; else q <<'SQL_RELEASE_EOF'
@@SQL_RELEASE@@
SQL_RELEASE_EOF
  fi
  [ "$DRY_RUN" = 1 ] || { [ "$(qnum "select count(*) from ops_0107_rollback_hold where released_at is null")" = 0 ] || die "some held record(s) could not be put back (see the output above)" 6
    [ "$(qnum "$TRAPS_SQL")" = 0 ] || die "the late-writer trap is still installed after the release" 6; }
}

do_release() {
  local new old have; new=$(load API_NEW_ID); old=$(load api_OLD_ID); have=$(ctr_image erpx_api)
  if ! ctr_running erpx_api || [ "$have" = "$old" ] || [ "$have" = "$(sget GUARD_IMAGE)" ] || [ -z "$new" ]; then die "the 0107 api is not the one running (or no 0107 image was recorded): releasing the hold now would re-expose private records. Use MODE=forward, or re-run steps 01-03 first. Nothing was done." 2; fi
  release_sql
}

do_forward() {
  PHASE=preflight
  [ -s "$STATE" ] && [ -n "$(sget NEW_api_ID)" ] || die "no saved 0107 images ($STATE has none): this host never ran MODE=full. Use steps 01-03 and then MODE=release." 2
  local svc
  for svc in $SERVICES; do
    local id; id=$(sget "NEW_${svc}_ID"); [ -n "$id" ] || die "the 0107 image of $svc was not saved" 2
    docker image inspect "$id" > /dev/null 2>&1 || die "the saved 0107 image of $svc ($id) no longer exists; re-run steps 01-03, then MODE=release" 2
  done
  echo "== ROLL FORWARD: stop the writers, release the hold, start the saved 0107 images"
  quiesce
  release_sql
  PHASE=start
  local name
  for svc in $SERVICES; do
    name=$(load "${svc}_NAME")
    run docker tag "$(sget "NEW_${svc}_ID")" "$name"
    run $COMPOSE up -d --no-deps --no-build "$svc"
    echo "$svc is on $(sget "NEW_${svc}_ID")"
    if [ "$svc" = api ] && [ "$DRY_RUN" != 1 ]; then wait_api_healthy "the 0107 api" || die "the 0107 api is not healthy; the hold has been released, so do NOT start the previous image; look at the log above" 4; fi
  done
  [ "$DRY_RUN" = 1 ] || { [ -f "$OVERRIDE" ] && mv "$OVERRIDE" "$OVERRIDE.$(date -u +%Y%m%dT%H%M%SZ).used"; sset FORWARDED_AT "$(date -u +%Y%m%dT%H%M%SZ)"; }
  PHASE=verify; PASS=0; WARN=0; FAIL=0
  if [ "$DRY_RUN" != 1 ]; then
    for svc in $SERVICES; do [ "$(ctr_image "$(container_of "$svc")")" = "$(sget "NEW_${svc}_ID")" ] && say PASS "erpx_$svc runs the 0107 image" || say FAIL "erpx_$svc does not run the 0107 image"; done
    [ "$(qnum "select count(*) from ops_0107_rollback_hold where released_at is null")" = 0 ] && say PASS "no record is held" || say FAIL "records are still held"
    echo "== SUMMARY: PASS=$PASS WARN=$WARN FAIL=$FAIL"
    [ "$FAIL" = 0 ] || { echo "RESULT: NO-GO"; return 1; }
  fi
  echo "RESULT: the 0107 code is live again and every held record is back under its course. Run 04_post_deploy_verify.sh."
}

case "$MODE" in
  full)
    gates
    prepare_guard
    record_new_images
    if [ "$DRY_RUN" != 1 ] && [ "$(ctr_image erpx_api)" = "$GUARD_IMAGE" ] && ctr_running erpx_api; then
      echo "== the previous api is already running from the guarded image: resuming (checking the hold, restoring whatever is left, verifying)"
      if [ "$(rev)" = 0107 ] && { [ "$(qnum "$PRIVATE_VISIBLE_SQL")" != 0 ] || [ "$(qnum "$TRAPS_SQL")" != 4 ]; }; then
        echo "!! the previous api is running while internship-private records are visible or the late-writer trap is missing: STOPPING IT NOW (fail closed)"
        stop_api_confirmed "Private records are visible over a running previous api."
        die "the previous api was stopped (confirmed) because internship-private records were visible. Run MODE=full again: it will stop the writers, hold the records and restore." 8
      fi
    else
      quiesce
      hold
    fi
    restore_images
    if [ "$DRY_RUN" = 1 ]; then DONE=1; echo "== DRY RUN complete: nothing was changed. Every line starting with + is a command the real run would execute."; exit 0; fi
    do_verify; DONE=1
    echo "== ROLLBACK (code only) DONE. The database is still at 0107. Records created by the 0107 features are hidden, not deleted: MODE=forward brings them back." ;;
  forward) do_forward; DONE=1 ;;
  verify)  do_verify; rc=$?; DONE=1; exit $rc ;;
  release) do_release; DONE=1 ;;
  *)       echo "set MODE to full, forward, verify or release"; exit 2 ;;
esac
