#!/bin/bash
# ERPX release 0107 (PR #180)  --  CODE-ONLY ROLLBACK.  The database STAYS at 0107 (nothing is downgraded, nothing is deleted).
#
# WHY A PLAIN IMAGE SWAP IS NOT SAFE (both proven by rehearsal on a copy of the schema, not guessed):
#   1. The previous code lists assessments, discussion threads, practicals and vivas by course alone and every student may list them. After a plain
#      swap an independent enrolee sees an internship's private quizzes, threads, practicals and vivas (and, as before this release, another
#      student's course results). So the private rows are first HELD: moved, unchanged, under a soft-deleted course that the previous code treats as
#      not found. Every move is recorded in ops_0107_rollback_hold; MODE=release puts each row back byte-for-byte.
#   2. The previous api image refuses to start against a database at 0107: its entrypoint runs `alembic upgrade head` (RUN_MIGRATIONS=true) and
#      alembic fails with "Can't locate revision identified by '0107'", so the container would crash-loop. The api is therefore restarted with
#      RUN_MIGRATIONS=false through a compose override file written to $PRE_DIR/.
#
# MODES (set MODE on the line below):
#   full      hold (only if the database is at 0107) -> restore all six previous images -> verify.   The normal choice.
#   hold      only the containment step.        images   only the six image swaps.        verify   read-only checks of the rolled-back state.
#   release   ROLL FORWARD: put the held rows back. Only after the 0107 code is running again (re-run steps 01-03 first). Refuses otherwise.
# DRY_RUN=1 prints every command and changes nothing.
#
# What it never does: alembic downgrade, drop a table or column, delete a row, restore the pre-release dump, touch backups or MinIO files.
MODE=${MODE:-PASTE_ONE_OF_full_hold_images_verify_release}
DRY_RUN=${DRY_RUN:-0}
set -euo pipefail
export LC_ALL=C
PRE_DIR=${PRE_DIR:-/opt/backups/pre-release}; ERPX_DIR=${ERPX_DIR:-/opt/erpx}   # production defaults; only overridden by the rehearsal harness

cd "$ERPX_DIR"
COMPOSE="docker compose -f docker-compose.prod.yml"
ENVF=$PRE_DIR/images-0107.env
OVERRIDE=$PRE_DIR/rollback-api-override.yml
SERVICES="api celery_worker celery_beat web student_portal trainer_portal"
run() { if [ "$DRY_RUN" = 1 ]; then echo "+ $*"; else "$@"; fi; }
q() { docker exec -i shared_postgres psql -X -U postgres -d erpx -v ON_ERROR_STOP=1 "$@"; }
qro() { docker exec -i -e PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=30000" shared_postgres psql -X -U postgres -d erpx -v ON_ERROR_STOP=1 "$@"; }
load() { grep -E "^$1=" "$ENVF" | tail -1 | cut -d= -f2-; }
rev() { qro -tA -c "select version_num from alembic_version" | tail -1; }
container_of() { case "$1" in api) echo erpx_api;; *) echo "erpx_$1";; esac; }

do_hold() {
  local r; r=$(rev)
  if [ "$r" != 0107 ]; then echo "database is at $r, not 0107: there is nothing to hold (the 0107 records do not exist); skipping the hold"; return 0; fi
  TS=$(date -u +%Y%m%dT%H%M%SZ)
  echo "== safety copy of the four tables the hold edits (small, custom format)"
  if [ "$DRY_RUN" = 1 ]; then echo "+ pg_dump -Fc of lms_assessments lms_discussion_threads exam_practicals exam_vivas > $PRE_DIR/pre-hold-$TS.dump"
  else docker exec shared_postgres pg_dump -U postgres -d erpx -Fc -t lms_assessments -t lms_discussion_threads -t exam_practicals -t exam_vivas > "$PRE_DIR/pre-hold-$TS.dump"; test -s "$PRE_DIR/pre-hold-$TS.dump"; ls -l "$PRE_DIR/pre-hold-$TS.dump"; fi
  echo "== HOLD: internship-private records out of reach of the previous code (one transaction, checks its own result)"
  if [ "$DRY_RUN" = 1 ]; then echo "+ psql < rollback_hold.sql (embedded below)"; else q <<'SQL_HOLD_EOF'
-- ERPX migration 0107 -- ROLLBACK CONTAINMENT ("hold").   WRITES to the database: run only as part of the code-only rollback procedure.
--
-- WHY. Release 0107 adds an internship_id to assessments, discussion threads, practicals and vivas. The previous application code does not
-- know that column: it lists these records by COURSE alone, and every student holds the permissions to list them. After a code-only
-- rollback an independent enrolee would therefore see (and could open) an internship's private quizzes, threads, practicals and vivas.
--
-- WHAT. Every row with internship_id IS NOT NULL is moved, unchanged, under a soft-deleted "holding" course of the same organization.
-- The previous code looks every course up first and treats a soft-deleted course as not found, so those rows become unreachable from it.
-- NOTHING is deleted or edited except the row's course_id; internship_id, children (questions, attempts, replies, results), scores, marks
-- and timestamps stay exactly as they are. Every move is written to ops_0107_rollback_hold so rollback_release.sql can put each row back.
--
-- SAFE TO RE-RUN: only rows not yet held are moved. All-or-nothing: one transaction, and it checks its own result before it commits.
-- Needs the schema at 0107 (the columns it reads). Takes row locks on the four tables for a moment; lock_timeout makes it give up
-- instead of waiting behind a long transaction.

\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

DO $$
BEGIN
  IF (SELECT version_num FROM alembic_version) <> '0107' THEN
    RAISE EXCEPTION 'the database is at % not 0107: nothing to hold (or run the hold only while the schema is at 0107)', (SELECT version_num FROM alembic_version);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS ops_0107_rollback_hold (
    id                 bigserial PRIMARY KEY,
    table_name         text        NOT NULL,
    row_id             uuid        NOT NULL,
    original_course_id uuid        NOT NULL,
    parking_course_id  uuid        NOT NULL,
    held_at            timestamptz NOT NULL DEFAULT now(),
    released_at        timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_ops_0107_rollback_hold_open ON ops_0107_rollback_hold (table_name, row_id) WHERE released_at IS NULL;

-- one soft-deleted holding course per organization that has something to hold
INSERT INTO courses (id, organization_id, title, slug, is_published, deleted_at)
SELECT gen_random_uuid(), o.organization_id, '[ROLLBACK HOLD 0107] internship-private records (hidden, do not restore)', 'rollback-hold-0107', false, now()
FROM (
    SELECT c.organization_id FROM lms_assessments t JOIN courses c ON c.id = t.course_id WHERE t.internship_id IS NOT NULL
    UNION SELECT c.organization_id FROM lms_discussion_threads t JOIN courses c ON c.id = t.course_id WHERE t.internship_id IS NOT NULL
    UNION SELECT c.organization_id FROM exam_practicals t JOIN courses c ON c.id = t.course_id WHERE t.internship_id IS NOT NULL
    UNION SELECT c.organization_id FROM exam_vivas t JOIN courses c ON c.id = t.course_id WHERE t.internship_id IS NOT NULL
) o
ON CONFLICT (organization_id, slug) DO NOTHING;

-- a holding course must be hidden, whatever happened to it before
UPDATE courses SET deleted_at = COALESCE(deleted_at, now()), is_published = false WHERE slug = 'rollback-hold-0107';

-- move + record, one statement per table (the ledger row is written from the same UPDATE ... RETURNING)
WITH moved AS (
    UPDATE lms_assessments t SET course_id = pc.id
    FROM courses c JOIN courses pc ON pc.organization_id = c.organization_id AND pc.slug = 'rollback-hold-0107'
    WHERE t.internship_id IS NOT NULL AND t.course_id = c.id AND c.id <> pc.id
    RETURNING t.id AS row_id, c.id AS original_course_id, pc.id AS parking_course_id
)
INSERT INTO ops_0107_rollback_hold (table_name, row_id, original_course_id, parking_course_id)
SELECT 'lms_assessments', row_id, original_course_id, parking_course_id FROM moved;

WITH moved AS (
    UPDATE lms_discussion_threads t SET course_id = pc.id
    FROM courses c JOIN courses pc ON pc.organization_id = c.organization_id AND pc.slug = 'rollback-hold-0107'
    WHERE t.internship_id IS NOT NULL AND t.course_id = c.id AND c.id <> pc.id
    RETURNING t.id AS row_id, c.id AS original_course_id, pc.id AS parking_course_id
)
INSERT INTO ops_0107_rollback_hold (table_name, row_id, original_course_id, parking_course_id)
SELECT 'lms_discussion_threads', row_id, original_course_id, parking_course_id FROM moved;

WITH moved AS (
    UPDATE exam_practicals t SET course_id = pc.id
    FROM courses c JOIN courses pc ON pc.organization_id = c.organization_id AND pc.slug = 'rollback-hold-0107'
    WHERE t.internship_id IS NOT NULL AND t.course_id = c.id AND c.id <> pc.id
    RETURNING t.id AS row_id, c.id AS original_course_id, pc.id AS parking_course_id
)
INSERT INTO ops_0107_rollback_hold (table_name, row_id, original_course_id, parking_course_id)
SELECT 'exam_practicals', row_id, original_course_id, parking_course_id FROM moved;

WITH moved AS (
    UPDATE exam_vivas t SET course_id = pc.id
    FROM courses c JOIN courses pc ON pc.organization_id = c.organization_id AND pc.slug = 'rollback-hold-0107'
    WHERE t.internship_id IS NOT NULL AND t.course_id = c.id AND c.id <> pc.id
    RETURNING t.id AS row_id, c.id AS original_course_id, pc.id AS parking_course_id
)
INSERT INTO ops_0107_rollback_hold (table_name, row_id, original_course_id, parking_course_id)
SELECT 'exam_vivas', row_id, original_course_id, parking_course_id FROM moved;

-- self-check: nothing internship-private may remain under a normal (visible) course. Any row left makes the whole transaction roll back.
DO $$
DECLARE left_over integer;
BEGIN
  SELECT (SELECT count(*) FROM lms_assessments t JOIN courses c ON c.id = t.course_id WHERE t.internship_id IS NOT NULL AND c.deleted_at IS NULL)
       + (SELECT count(*) FROM lms_discussion_threads t JOIN courses c ON c.id = t.course_id WHERE t.internship_id IS NOT NULL AND c.deleted_at IS NULL)
       + (SELECT count(*) FROM exam_practicals t JOIN courses c ON c.id = t.course_id WHERE t.internship_id IS NOT NULL AND c.deleted_at IS NULL)
       + (SELECT count(*) FROM exam_vivas t JOIN courses c ON c.id = t.course_id WHERE t.internship_id IS NOT NULL AND c.deleted_at IS NULL)
    INTO left_over;
  IF left_over <> 0 THEN
    RAISE EXCEPTION 'hold incomplete: % internship-private row(s) are still under a visible course; rolled back, nothing changed', left_over;
  END IF;
END $$;

SELECT table_name, count(*) FILTER (WHERE released_at IS NULL) AS held_now, count(*) AS ever_held FROM ops_0107_rollback_hold GROUP BY table_name ORDER BY table_name;
COMMIT;
SQL_HOLD_EOF
  fi
}

do_images() {
  test -s "$ENVF" || { echo "$ENVF is missing: no saved images to restore"; exit 2; }
  if [ "$DRY_RUN" != 1 ]; then
    printf 'services:\n  api:\n    environment:\n      RUN_MIGRATIONS: "false"\n' > "$OVERRIDE"
  else echo "+ write $OVERRIDE (api: RUN_MIGRATIONS=false)"; fi
  for svc in $SERVICES; do
    name=$(load "${svc}_NAME"); id=$(load "${svc}_OLD_ID")
    [ -n "$name" ] && [ -n "$id" ] || { echo "no saved image for $svc in $ENVF; stopping"; exit 2; }
    run docker image inspect "$id" > /dev/null
    run docker tag "$id" "$name"
    if [ "$svc" = api ]; then run docker compose -f docker-compose.prod.yml -f "$OVERRIDE" up -d --no-deps --no-build api
    else run $COMPOSE up -d --no-deps --no-build "$svc"; fi
    echo "$svc restored to $id"
    if [ "$svc" = api ] && [ "$DRY_RUN" != 1 ]; then
      echo "== wait for the previous api to be healthy (up to 4 minutes)"
      st=none; for i in $(seq 1 48); do st=$(docker inspect -f '{{.State.Health.Status}}' erpx_api 2>/dev/null || echo none); [ "$st" = healthy ] && break; sleep 5; done
      echo "api health: $st"; [ "$st" = healthy ] || { docker logs --tail 40 erpx_api 2>&1; echo "!! the previous api is not healthy; stop and decide (the database is untouched at $(rev))"; exit 4; }
    fi
  done
}

do_verify() {
  echo "== VERIFY (read-only)"
  echo "database revision: $(rev)   (a code-only rollback leaves it at 0107)"
  echo "api health: $(docker exec erpx_api python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/api/v1/health').status)" 2>&1 | tail -1)"
  for svc in $SERVICES; do
    c=$(container_of "$svc"); want=$(load "${svc}_OLD_ID"); have=$(docker inspect -f '{{.Image}}' "$c" 2>&1)
    [ "$want" = "$have" ] && echo "  $c runs the previous image: yes" || echo "  $c runs the previous image: NO (wanted $want, has $have)"
  done
  echo "private rows still under a VISIBLE course (must be 0):"
  qro -tA -c "select (select count(*) from lms_assessments t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is null) + (select count(*) from lms_discussion_threads t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is null) + (select count(*) from exam_practicals t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is null) + (select count(*) from exam_vivas t join courses c on c.id=t.course_id where t.internship_id is not null and c.deleted_at is null)"
  echo "hold ledger (held_now = records currently hidden):"
  qro -c "select table_name, count(*) filter (where released_at is null) as held_now, count(*) as ever_held from ops_0107_rollback_hold group by 1 order by 1" 2>&1 | sed 's/^/  /'
  $COMPOSE ps --format 'table {{.Name}}\t{{.Status}}' | head -20
}

do_release() {
  new=$(load "API_NEW_ID"); old=$(load "api_OLD_ID"); have=$(docker inspect -f '{{.Image}}' erpx_api)
  if [ "$have" = "$old" ] || [ -z "$new" ]; then echo "the PREVIOUS api is running (or no new image was recorded): releasing the hold now would re-expose private records. Re-run steps 01-03 first; nothing was done"; exit 2; fi
  [ "$(rev)" = 0107 ] || { echo "the database is not at 0107; nothing was done"; exit 2; }
  echo "== RELEASE: put every held record back under its original course"
  if [ "$DRY_RUN" = 1 ]; then echo "+ psql < rollback_release.sql (embedded below)"; else q <<'SQL_RELEASE_EOF'
-- ERPX migration 0107 -- ROLL-FORWARD: release the rollback hold.   WRITES to the database.
--
-- Run it only when the 0107 application code is running again (never while the previous code is live: that would re-expose the records).
-- Puts every held row back under the course it came from (course_id only; nothing else about the rows changed while they were held),
-- and marks the ledger rows released. A row whose course_id was changed by somebody in the meantime is left where it is and reported.
-- The ledger table and the soft-deleted holding courses are kept (they are the audit trail); remove them later by hand if you wish.

\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

DO $$
BEGIN
  IF (SELECT version_num FROM alembic_version) <> '0107' THEN
    RAISE EXCEPTION 'the database is at % not 0107', (SELECT version_num FROM alembic_version);
  END IF;
  IF to_regclass('ops_0107_rollback_hold') IS NULL THEN
    RAISE EXCEPTION 'ops_0107_rollback_hold does not exist: nothing was held';
  END IF;
END $$;

UPDATE lms_assessments t SET course_id = h.original_course_id FROM ops_0107_rollback_hold h
 WHERE h.table_name = 'lms_assessments' AND h.row_id = t.id AND h.released_at IS NULL AND t.course_id = h.parking_course_id;
UPDATE lms_discussion_threads t SET course_id = h.original_course_id FROM ops_0107_rollback_hold h
 WHERE h.table_name = 'lms_discussion_threads' AND h.row_id = t.id AND h.released_at IS NULL AND t.course_id = h.parking_course_id;
UPDATE exam_practicals t SET course_id = h.original_course_id FROM ops_0107_rollback_hold h
 WHERE h.table_name = 'exam_practicals' AND h.row_id = t.id AND h.released_at IS NULL AND t.course_id = h.parking_course_id;
UPDATE exam_vivas t SET course_id = h.original_course_id FROM ops_0107_rollback_hold h
 WHERE h.table_name = 'exam_vivas' AND h.row_id = t.id AND h.released_at IS NULL AND t.course_id = h.parking_course_id;

-- mark released exactly the ledger rows whose record is back under its original course
UPDATE ops_0107_rollback_hold h SET released_at = now()
 WHERE h.released_at IS NULL AND (
       (h.table_name = 'lms_assessments'        AND EXISTS (SELECT 1 FROM lms_assessments t        WHERE t.id = h.row_id AND t.course_id = h.original_course_id))
    OR (h.table_name = 'lms_discussion_threads' AND EXISTS (SELECT 1 FROM lms_discussion_threads t WHERE t.id = h.row_id AND t.course_id = h.original_course_id))
    OR (h.table_name = 'exam_practicals'        AND EXISTS (SELECT 1 FROM exam_practicals t        WHERE t.id = h.row_id AND t.course_id = h.original_course_id))
    OR (h.table_name = 'exam_vivas'             AND EXISTS (SELECT 1 FROM exam_vivas t             WHERE t.id = h.row_id AND t.course_id = h.original_course_id)));

SELECT table_name, count(*) FILTER (WHERE released_at IS NULL) AS still_held_NEEDS_ATTENTION_if_not_zero, count(*) FILTER (WHERE released_at IS NOT NULL) AS released
FROM ops_0107_rollback_hold GROUP BY table_name ORDER BY table_name;
COMMIT;
SQL_RELEASE_EOF
  fi
}

case "$MODE" in
  full)    do_hold; do_images; do_verify; echo "== ROLLBACK (code only) DONE. The database is still at 0107. Records created by the 0107 features are hidden, not deleted." ;;
  hold)    do_hold ;;
  images)  do_images ;;
  verify)  do_verify ;;
  release) do_release ;;
  *)       echo "set MODE to full, hold, images, verify or release"; exit 2 ;;
esac
