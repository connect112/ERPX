#!/bin/bash
# ERPX release 0107 (PR #180)  --  STEP 4: READ-ONLY post-deployment verification. Changes nothing (same read-only database session as the preflight).
# Run after Step 3, then do the manual checklist (RELEASE_CHECKLIST_0107.md part 3). Paste into Run Command > AWS-RunShellScript.
# Every line is PASS / WARN / FAIL; the last line is the automatic part of the GO/NO-GO.
#
# EXIT STATUS: 0 = no FAIL (warnings may exist: they are listed and counted separately); 1 = at least one FAIL, or the script stopped before it
# finished: the last line then says NO-GO. A query that cannot run (database unreachable, invalid SQL, a missing table, a timeout) is a FAIL with the
# database's own error message: it is never read as an empty result, a zero or a success.
DRY_RUN=${DRY_RUN:-0}
export LC_ALL=C
PRE_DIR=${PRE_DIR:-/opt/backups/pre-release}; ERPX_DIR=${ERPX_DIR:-/opt/erpx}   # production defaults; only overridden by the rehearsal harness
RO_OPTS="-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=3000 -c idle_in_transaction_session_timeout=60000"
q() { docker exec -i -e PGOPTIONS="$RO_OPTS" shared_postgres psql -X -U postgres -d erpx -v ON_ERROR_STOP=1 "$@"; }
PASS=0; WARN=0; FAIL=0; FINISHED=0
say() { printf '  [%s] %s\n' "$1" "$2"; case "$1" in PASS) PASS=$((PASS+1));; WARN) WARN=$((WARN+1));; FAIL) FAIL=$((FAIL+1));; esac; }
# If anything ends the script early, the last line still says NO-GO.
trap '[ "$FINISHED" = 1 ] || { echo "RESULT: NO-GO (the script stopped before it finished: treat this as a failure)"; }' EXIT
# qs LABEL SQL [num|text]: run one read-only query that returns one value. Sets QS and returns 0, or records a FAIL (with the database error) and returns 1.
# Always call it directly (never inside $(...)), so the FAIL is counted.
qs() {
  local label=$1 sql=$2 kind=${3:-num} out rc
  QS=""
  out=$(q -tA -c "$sql" 2>&1); rc=$?
  if [ "$rc" -ne 0 ]; then say FAIL "$label: the query failed ($(printf '%s' "$out" | tr '\n' ' ' | cut -c1-170))"; return 1; fi
  QS=$(printf '%s\n' "$out" | tail -1)
  if [ "$kind" = num ] && ! [[ "$QS" =~ ^[0-9]+$ ]]; then say FAIL "$label: unexpected query result '${QS:0:60}'"; QS=""; return 1; fi
  return 0
}
if [ "$DRY_RUN" = 1 ]; then FINISHED=1; echo "DRY RUN: read-only checks of revision, health, containers, row counts, logs and PDF libraries; nothing is changed."; exit 0; fi

echo "== 1. database and application"
if qs "read-only database session" "show transaction_read_only" text; then
  [ "$QS" = on ] && say PASS "every database session of this script is read-only (enforced by PostgreSQL)" || say FAIL "the database session is NOT read-only ('$QS'): stop, nothing was changed"
fi
if qs "alembic_version" "select version_num from alembic_version" text; then
  [ "$QS" = 0107 ] && say PASS "database revision is 0107" || say FAIL "database revision is '$QS', expected 0107"
fi
H=$(docker exec -e PYTHONDONTWRITEBYTECODE=1 erpx_api python -B -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/api/v1/health').status)" 2>&1 | tail -1)
[ "$H" = 200 ] && say PASS "api health endpoint answers 200" || say FAIL "api health endpoint: $H"
for c in erpx_api erpx_celery_worker erpx_celery_beat erpx_web erpx_student_portal erpx_trainer_portal; do
  S=$(docker inspect -f '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}nohealthcheck{{end}}' $c 2>&1)
  case "$S" in running/healthy|running/nohealthcheck) say PASS "$c $S";; *) say FAIL "$c $S";; esac
done
RESTARTS=$(docker inspect -f '{{.Name}} restarts={{.RestartCount}}' erpx_api erpx_celery_worker erpx_celery_beat 2>&1 | tr '\n' ' '); echo "  info: $RESTARTS"

echo; echo "== 2. data: nothing shrank, nothing is parked, nothing is orphaned"
BASE=$PRE_DIR/baseline-counts-0107.txt
if [ -s "$BASE" ]; then
  while read -r t before <&3; do   # fd 3: the docker exec inside must not eat the rest of the file from stdin
    if ! [[ "$t" =~ ^[a-z_][a-z0-9_]*$ ]] || ! [[ "$before" =~ ^[0-9]+$ ]]; then say FAIL "baseline file line is not 'table count': '${t:0:40} ${before:0:20}'"; continue; fi
    if qs "row count of $t" "select count(*) from $t"; then
      if [ "$QS" -ge "$before" ]; then say PASS "$t rows $before -> $QS"; else say FAIL "$t SHRANK: $before -> $QS"; fi
    fi
  done 3< "$BASE"
else
  say WARN "no baseline file $BASE (Step 1 writes it): row counts not compared"
fi
# The rollback ledger only exists after a rollback has been run. On a first deployment it is not there: that is ZERO active holds, not an error.
# (Two statements on purpose: PostgreSQL resolves a table name when it plans a query, even inside a CASE branch that would never run, so the
# count may only be asked once the table is known to exist.)
if qs "rollback ledger lookup" "select coalesce(to_regclass('ops_0107_rollback_hold')::text, '')" text; then
  if [ -z "$QS" ]; then
    say PASS "no rollback ledger exists (no rollback was ever run): zero active holds"
  elif qs "active rollback holds" "select count(*) from ops_0107_rollback_hold where released_at is null"; then
    [ "$QS" = 0 ] && say PASS "the rollback ledger exists and no hold is active (internship-private records are under their own courses)" || say FAIL "$QS record(s) are parked by a rollback hold: this is not a healthy forward state (run 90_rollback_code_only.sh with MODE=release)"
  fi
fi
if qs "internship-scoped records under deleted courses" "select (select count(*) from lms_assessments t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is not null) + (select count(*) from lms_discussion_threads t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is not null) + (select count(*) from exam_practicals t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is not null) + (select count(*) from exam_vivas t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is not null)"; then
  [ "$QS" = 0 ] && say PASS "no internship-scoped record sits under a deleted course" || say WARN "$QS internship-scoped record(s) sit under a deleted course"
fi
if qs "long transactions" "select count(*) from pg_stat_activity where xact_start is not null and now()-xact_start > interval '5 minutes' and pid <> pg_backend_pid()"; then
  [ "$QS" = 0 ] && say PASS "no transaction open longer than 5 minutes" || say WARN "$QS long transaction(s)"
fi

echo; echo "== 3. logs (last 20 minutes): errors that would matter to students, payments, e-mail or PDFs"
for c in erpx_api erpx_celery_worker; do
  LOGS=$(docker logs --since 20m $c 2>&1); rc=$?
  if [ "$rc" -ne 0 ]; then say FAIL "$c: its log could not be read ($(printf '%s' "$LOGS" | tr '\n' ' ' | cut -c1-120))"; continue; fi
  N=$(printf '%s\n' "$LOGS" | grep -ciE 'traceback|"level": *"error"|\[error ' || true)
  [ "${N:-0}" -eq 0 ] && say PASS "$c: no error lines in 20 minutes" || { say WARN "$c: $N error line(s) in 20 minutes (first 3 below)"; printf '%s\n' "$LOGS" | grep -iE 'traceback|"level": *"error"|\[error ' | head -3 | cut -c1-220; }
  if [ "$c" = erpx_api ]; then
    W=$(printf '%s\n' "$LOGS" | grep -ciE 'cashfree.*(error|failed)|webhook.*(error|failed|invalid)' || true)
    [ "${W:-0}" -eq 0 ] && say PASS "no payment/webhook failures logged in 20 minutes" || say FAIL "$W payment/webhook failure line(s) in 20 minutes: look at them before you continue"
  else
    M=$(printf '%s\n' "$LOGS" | grep -ciE 'smtp.*(error|refused|timeout)|send.*failed' || true)
    [ "${M:-0}" -eq 0 ] && say PASS "no e-mail sending failures logged in 20 minutes" || say WARN "$M e-mail failure line(s) in 20 minutes"
  fi
done

echo; echo "== 4. PDF libraries in the running containers (in memory only: nothing is written)"
for c in erpx_api erpx_celery_worker; do
  OUT=$(docker exec -e PYTHONDONTWRITEBYTECODE=1 $c python -B -c "
import io, importlib.metadata as m
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
d = svg2rlg(io.BytesIO(b'<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"40\" height=\"20\"><rect width=\"40\" height=\"20\" fill=\"#1f3a8a\"/></svg>'))
pdf = renderPDF.drawToString(d)
print('reportlab', m.version('reportlab'), 'svglib', m.version('svglib'), 'svg->pdf bytes', len(pdf), 'ok' if pdf[:4] == b'%PDF' else 'NOT A PDF')
" 2>&1 | tail -1)
  echo "  $c: $OUT"
  echo "$OUT" | grep -q "reportlab 4.4.3 svglib 2.3.1.*ok" && say PASS "$c renders SVG to PDF with reportlab 4.4.3 / svglib 2.3.1" || say FAIL "$c PDF library check failed"
done

echo; echo "== 5. backups are still running"
[ "$(systemctl is-active offsite-backup.timer 2>/dev/null)" = active ] && say PASS "offsite-backup.timer is active" || say FAIL "offsite-backup.timer is not active"
ls -l $PRE_DIR/erpx-before-0107-*.dump 2>/dev/null | sed 's/^/  pre-release dump: /'

FINISHED=1
echo; echo "== SUMMARY: PASS=$PASS WARN=$WARN FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo "RESULT: NO-GO for declaring the release good: see the FAIL lines and RELEASE_CHECKLIST_0107.md part 4 (rollback decision)"
  echo "== done (nothing was changed)"; exit 1
fi
echo "RESULT: automatic checks pass (WARN lines, if any, are listed above); complete the manual checklist (part 3) before you declare the release good"
echo "== done (nothing was changed)"; exit 0
