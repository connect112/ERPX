#!/bin/bash
# ERPX release 0107 (PR #180)  --  STEP 4: READ-ONLY post-deployment verification. Changes nothing (same read-only database session as the preflight).
# Run after Step 3, then do the manual checklist (RELEASE_CHECKLIST_0107.md part 3). Paste into Run Command > AWS-RunShellScript.
# Every line is PASS / WARN / FAIL; the last line is the automatic part of the GO/NO-GO.
DRY_RUN=${DRY_RUN:-0}
export LC_ALL=C
PRE_DIR=${PRE_DIR:-/opt/backups/pre-release}; ERPX_DIR=${ERPX_DIR:-/opt/erpx}   # production defaults; only overridden by the rehearsal harness
RO_OPTS="-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=3000 -c idle_in_transaction_session_timeout=60000"
q() { docker exec -i -e PGOPTIONS="$RO_OPTS" shared_postgres psql -X -U postgres -d erpx -v ON_ERROR_STOP=1 "$@"; }
PASS=0; WARN=0; FAIL=0
say() { printf '  [%s] %s\n' "$1" "$2"; case "$1" in PASS) PASS=$((PASS+1));; WARN) WARN=$((WARN+1));; FAIL) FAIL=$((FAIL+1));; esac; }
if [ "$DRY_RUN" = 1 ]; then echo "DRY RUN: read-only checks of revision, health, containers, row counts, logs and PDF libraries; nothing is changed."; exit 0; fi

echo "== 1. database and application"
REV=$(q -tA -c "select version_num from alembic_version" | tail -1)
[ "$REV" = 0107 ] && say PASS "database revision is 0107" || say FAIL "database revision is '$REV', expected 0107"
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
    now=$(q -tA -c "select count(*) from $t" | tail -1)
    if [ "$now" -ge "$before" ]; then say PASS "$t rows $before -> $now"; else say FAIL "$t SHRANK: $before -> $now"; fi
  done 3< "$BASE"
else
  say WARN "no baseline file $BASE (Step 1 writes it): row counts not compared"
fi
HELD=$(q -tA -c "select case when to_regclass('ops_0107_rollback_hold') is null then 0 else (select count(*) from ops_0107_rollback_hold where released_at is null) end" | tail -1)
[ "$HELD" = 0 ] && say PASS "no rollback hold is active (internship-private records are under their own courses)" || say FAIL "$HELD record(s) are parked by a rollback hold: this is not a healthy forward state"
PRIV=$(q -tA -c "select (select count(*) from lms_assessments t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is not null) + (select count(*) from lms_discussion_threads t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is not null) + (select count(*) from exam_practicals t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is not null) + (select count(*) from exam_vivas t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is not null)" | tail -1)
[ "$PRIV" = 0 ] && say PASS "no internship-scoped record sits under a deleted course" || say WARN "$PRIV internship-scoped record(s) sit under a deleted course"
OPENX=$(q -tA -c "select count(*) from pg_stat_activity where xact_start is not null and now()-xact_start > interval '5 minutes' and pid <> pg_backend_pid()" | tail -1)
[ "$OPENX" = 0 ] && say PASS "no transaction open longer than 5 minutes" || say WARN "$OPENX long transaction(s)"

echo; echo "== 3. logs (last 20 minutes): errors that would matter to students, payments, e-mail or PDFs"
for c in erpx_api erpx_celery_worker; do
  N=$(docker logs --since 20m $c 2>&1 | grep -ciE 'traceback|"level": *"error"|\[error ' || true)
  [ "${N:-0}" -eq 0 ] && say PASS "$c: no error lines in 20 minutes" || { say WARN "$c: $N error line(s) in 20 minutes (first 3 below)"; docker logs --since 20m $c 2>&1 | grep -iE 'traceback|"level": *"error"|\[error ' | head -3 | cut -c1-220; }
done
W=$(docker logs --since 20m erpx_api 2>&1 | grep -ciE 'cashfree.*(error|failed)|webhook.*(error|failed|invalid)' || true)
[ "${W:-0}" -eq 0 ] && say PASS "no payment/webhook failures logged in 20 minutes" || say FAIL "$W payment/webhook failure line(s) in 20 minutes: look at them before you continue"
M=$(docker logs --since 20m erpx_celery_worker 2>&1 | grep -ciE 'smtp.*(error|refused|timeout)|send.*failed' || true)
[ "${M:-0}" -eq 0 ] && say PASS "no e-mail sending failures logged in 20 minutes" || say WARN "$M e-mail failure line(s) in 20 minutes"

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

echo; echo "== SUMMARY: PASS=$PASS WARN=$WARN FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then echo "RESULT: NO-GO for declaring the release good: see FAIL lines and RELEASE_CHECKLIST_0107.md part 4 (rollback decision)"; else echo "RESULT: automatic checks pass; complete the manual checklist (part 3) before you declare the release good"; fi
echo "== done (nothing was changed)"
