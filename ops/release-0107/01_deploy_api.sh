#!/bin/bash
# ERPX release 0107 (PR #180)  --  STEP 1: move the source to the merged commit, save rollback targets, build and recreate ONLY the api container.
# Starting the new api image applies migration 0107 (RUN_MIGRATIONS=true in docker-compose.prod.yml) and the idempotent RBAC seed.
# Worker, beat, web, student portal, trainer portal, MinIO, Postgres, Redis, Caddy and Pentrix are NOT touched.
#
# It refuses to start unless: the database is at the revision you expect, the api is healthy, disk is sufficient, the newest off-server backup
# is under 27 h old with SHA256SUMS, and /opt/erpx can fast-forward to exactly SHA. Before anything changes it saves (a) a compressed dump of the
# erpx database (verified readable), (b) the running image ids and (c) row-count baselines that 04_post_deploy_verify.sh compares against.
# If a check fails it stops and says what to do; it never rolls back by itself (see 90_rollback_code_only.sh).
#
# RUN ONLY AFTER: the PR is merged by you, 00_preflight_readonly.sh shows no FAIL, and you approved. Paste into Run Command > AWS-RunShellScript on the
# production instance only, after setting the two values below. DRY_RUN=1 prints every command without running it.
SHA=${SHA:-PASTE_THE_40_CHARACTER_MERGE_COMMIT_HERE}
EXPECT_REV_BEFORE=${EXPECT_REV_BEFORE:-PASTE_THE_REVISION_THE_PREFLIGHT_REPORTED}
DRY_RUN=${DRY_RUN:-0}
set -euo pipefail
export LC_ALL=C
PRE_DIR=${PRE_DIR:-/opt/backups/pre-release}; ERPX_DIR=${ERPX_DIR:-/opt/erpx}   # production defaults; only overridden by the rehearsal harness

BUCKET=pentrix-erpx-backups-373384939117
COMPOSE="docker compose -f docker-compose.prod.yml"
run() { if [ "$DRY_RUN" = 1 ]; then echo "+ $*"; else "$@"; fi; }
q() { docker exec -i -e PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=3000" shared_postgres psql -X -U postgres -d erpx -v ON_ERROR_STOP=1 "$@"; }

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "SHA is not a 40-character commit id; nothing was done"; exit 2; }
[[ "$EXPECT_REV_BEFORE" =~ ^0[0-9]{3}$ ]] || { echo "EXPECT_REV_BEFORE is not set (use the revision the preflight printed); nothing was done"; exit 2; }
cd "$ERPX_DIR"

echo "== gates (all read-only)"
CUR=$(q -tA -c "select version_num from alembic_version" | tail -1)
echo "database revision: $CUR (expected $EXPECT_REV_BEFORE)"
[ "$CUR" = "$EXPECT_REV_BEFORE" ] || { echo "the database is not at the expected revision; stopping"; exit 3; }
avail=$(df -B1 --output=avail / | tail -1 | tr -d ' ')
dbsize=$(q -tA -c "select pg_database_size(current_database())" | tail -1); need=$(( dbsize * 2 )); [ "$need" -lt 4000000000 ] && need=4000000000
echo "free disk: $((avail/1024/1024)) MiB (need $((need/1024/1024)) MiB)"
[ "$avail" -ge "$need" ] || { echo "not enough free disk; stopping before any build"; exit 3; }
[ "$(docker inspect -f '{{.State.Health.Status}}' erpx_api)" = healthy ] || { echo "erpx_api is not healthy before the release; stopping"; exit 3; }
NEWEST=$(aws s3 ls "s3://$BUCKET/daily/" | awk '$1=="PRE"{print $2}' | tr -d '/' | sort | tail -1)
AGE_H=$(( ( $(date -u +%s) - $(date -u -d "$NEWEST 03:30" +%s) ) / 3600 ))
echo "newest off-server backup: $NEWEST ($AGE_H h old)"
[ "$AGE_H" -le 27 ] || { echo "the newest off-server backup is older than 27 h; stopping"; exit 3; }
aws s3 ls "s3://$BUCKET/daily/$NEWEST/" | grep -q SHA256SUMS || { echo "the newest off-server backup has no SHA256SUMS (unfinished); stopping"; exit 3; }
LONGX=$(q -tA -c "select count(*) from pg_stat_activity where xact_start is not null and now()-xact_start > interval '5 minutes' and pid <> pg_backend_pid()" | tail -1)
[ "$LONGX" = 0 ] || { echo "$LONGX transaction(s) open for over 5 minutes; stopping (the migration needs brief table locks)"; exit 3; }
test -z "$(git --no-optional-locks status --porcelain --untracked-files=no)" || { echo "tracked local changes in /opt/erpx; stopping"; exit 3; }

echo "== source: $(git rev-parse --short HEAD) -> ${SHA:0:7}"
run git fetch origin master
run git merge --ff-only "$SHA"
if [ "$DRY_RUN" != 1 ]; then
  test "$(git rev-parse HEAD)" = "$SHA" || { echo "/opt/erpx is not at $SHA after the fast-forward; stopping"; exit 3; }
  test -f apps/api/alembic/versions/0107_learning_integration.py || { echo "0107 is not in this commit; wrong SHA? stopping"; exit 3; }
  [ "$(grep -lE 'down_revision.*"0107"' apps/api/alembic/versions/*.py 2>/dev/null | wc -l)" = 0 ] || { echo "a migration newer than 0107 is in this commit; this checklist covers 0107 only; stopping"; exit 3; }
fi

TS=$(date -u +%Y%m%dT%H%M%SZ)
run mkdir -p $PRE_DIR
ENVF=$PRE_DIR/images-0107.env
[ -f "$ENVF" ] && run mv "$ENVF" "$ENVF.$TS.old"
echo "== rollback targets: the images running now"
if [ "$DRY_RUN" != 1 ]; then
  : > "$ENVF"
  for pair in "api erpx_api" "celery_worker erpx_celery_worker" "celery_beat erpx_celery_beat" "web erpx_web" "student_portal erpx_student_portal" "trainer_portal erpx_trainer_portal"; do
    set -- $pair
    old=$(docker inspect -f '{{.Image}}' "$2"); name=$(docker inspect -f '{{.Config.Image}}' "$2")
    docker tag "$old" "erpx-rollback/$1:pre-0107-$TS"
    printf '%s_NAME=%s\n%s_OLD_ID=%s\n' "$1" "$name" "$1" "$old" >> "$ENVF"
  done
  printf 'TS=%s\nSHA=%s\nREV_BEFORE=%s\n' "$TS" "$SHA" "$CUR" >> "$ENVF"
  cat "$ENVF"
else
  echo "+ tag the six running images as erpx-rollback/<service>:pre-0107-$TS and write $ENVF"
fi

echo "== row-count baselines (04_post_deploy_verify.sh checks that nothing shrank)"
BASE=$PRE_DIR/baseline-counts-0107.txt
if [ "$DRY_RUN" != 1 ]; then
  : > "$BASE"
  for t in internship_payment_orders internship_payment_transactions internship_payment_webhooks internship_financial_documents internship_onboarding_applications offer_letters offer_letter_deliveries accounting_payments accounting_receipts internship_receipt_designs lms_certificates internship_certificate_eligibility workshop_exams workshop_exam_attendees exam_attempts lms_enrollments our_internship_selections students users lms_assessments lms_assessment_attempts course_resources exam_practicals exam_vivas lms_discussion_threads; do
    if [ "$(q -tA -c "select to_regclass('$t') is not null" | tail -1)" = t ]; then echo "$t $(q -tA -c "select count(*) from $t" | tail -1)" >> "$BASE"; fi
  done
  cat "$BASE"
fi

echo "== pre-migration dump of the erpx database (custom format, compressed)"
DUMP=$PRE_DIR/erpx-before-0107-$TS.dump
if [ "$DRY_RUN" != 1 ]; then
  docker exec shared_postgres pg_dump -U postgres -d erpx -Fc -Z 6 > "$DUMP"
  test -s "$DUMP"
  docker exec -i shared_postgres pg_restore --list < "$DUMP" | sed -n '1,3p'   # sed reads everything: head would break the pipe under pipefail
  ls -l "$DUMP"; sha256sum "$DUMP" | tee "$DUMP.sha256"
  printf 'DUMP=%s\n' "$DUMP" >> "$ENVF"
else
  echo "+ docker exec shared_postgres pg_dump -U postgres -d erpx -Fc -Z 6 > $DUMP  (then pg_restore --list and sha256sum)"
fi

echo "== build (build cache only is cleared first, as in every earlier deploy; images and volumes are never pruned)"
run docker builder prune -af
run $COMPOSE build api
echo "== recreate api only (applies migration 0107)"
run $COMPOSE up -d --no-deps api

if [ "$DRY_RUN" = 1 ]; then echo "DRY RUN finished: nothing was changed"; exit 0; fi
echo "== wait for healthy (up to 4 minutes)"
st=none
for i in $(seq 1 48); do
  st=$(docker inspect -f '{{.State.Health.Status}}' erpx_api 2>/dev/null || echo none)
  [ "$st" = healthy ] && break
  sleep 5
done
echo "api health: $st"
if [ "$st" != healthy ]; then
  echo "!! api did not become healthy. Logs:"; docker logs --tail 60 erpx_api 2>&1
  echo "!! Do NOT start anything else. The migration runs in one transaction: if it failed, the database is still at $CUR."
  echo "!! Check: select version_num from alembic_version. Then run 90_rollback_code_only.sh with MODE=full (it skips the hold while the database is not at 0107)."
  exit 4
fi
printf 'API_NEW_ID=%s\n' "$(docker inspect -f '{{.Image}}' erpx_api)" >> "$ENVF"

echo "== CHECKPOINT C1"
echo "alembic_version: $(q -tA -c 'select version_num from alembic_version' | tail -1)   (expect 0107)"
docker exec erpx_api python -c "import urllib.request;print('health:',urllib.request.urlopen('http://localhost:8000/api/v1/health').read().decode()[:120])"
q -tA -c "select 'new columns present: ' || count(*) || ' of 10' from information_schema.columns where (table_name, column_name) in (('exam_practicals','internship_id'),('exam_vivas','internship_id'),('lms_discussion_threads','internship_id'),('lms_assessments','internship_id'),('lms_assessments','show_result'),('lms_assessment_attempts','answers'),('lms_assessment_attempts','total_marks'),('course_resources','storage_key'),('workshop_exam_attendees','selection_id'),('course_resources','uploaded_by_user_id'))"
q -tA -c "select 'lms_assessment_questions exists: ' || (to_regclass('lms_assessment_questions') is not null)"
q -tA -c "select 'attendees linked to a selection: ' || count(*) filter (where selection_id is not null) || ' of ' || count(*) from workshop_exam_attendees"
echo "api errors in the last 3 minutes:"; docker logs --since 3m erpx_api 2>&1 | grep -iE 'error|traceback' | head -5 || true
$COMPOSE ps --format 'table {{.Name}}\t{{.Status}}' | head -20
echo "== STEP 1 DONE. Worker, beat and the three frontends are still on the previous version: the schema change is additive, but continue with steps 2 and 3 in the same window (the old screens have not been tested against the new API)."
