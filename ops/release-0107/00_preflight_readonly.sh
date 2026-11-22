#!/bin/bash
# ERPX release 0107 (PR #180)  --  STEP 0: READ-ONLY production preflight.  Prints facts; changes NOTHING.
#
# What makes it read-only (all of these hold at the same time):
#   1. every database call runs in a session that PostgreSQL itself forces read-only (default_transaction_read_only=on): an INSERT, UPDATE, DELETE,
#      DDL or any other write is refused by the database with "cannot execute ... in a read-only transaction";
#   2. the two embedded SQL reports also open with BEGIN TRANSACTION READ ONLY and end with ROLLBACK;
#   3. statement_timeout, lock_timeout and idle_in_transaction_session_timeout stop it from ever holding or waiting for a lock;
#   4. host commands are limited to reading: df, du, date, head, systemctl list-timers / is-active, docker inspect, git rev-parse,
#      git --no-optional-locks status, `aws s3 ls` (list only), and one docker exec: `alembic heads` (reads the migration files; run with
#      PYTHONDONTWRITEBYTECODE=1 so not even a .pyc cache is written inside the container). It never runs an alembic upgrade/downgrade/stamp,
#      never starts, stops, restarts, builds or tags a container, never writes a file, never edits a backup unit/timer/config, never runs
#      git fetch/pull/checkout.
#   5. output holds ids, titles, counts and file names only: no names, e-mails, phone numbers or secrets.
#
# Paste into AWS Systems Manager > Run Command > AWS-RunShellScript, target the production instance only. Set DRY_RUN=1 on the next line to
# only print what it would run.
DRY_RUN=${DRY_RUN:-0}
export LC_ALL=C
PRE_DIR=${PRE_DIR:-/opt/backups/pre-release}; ERPX_DIR=${ERPX_DIR:-/opt/erpx}   # production defaults; only overridden by the rehearsal harness
BUCKET=pentrix-erpx-backups-373384939117
RO_OPTS="-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=3000 -c idle_in_transaction_session_timeout=60000"
q() { docker exec -i -e PGOPTIONS="$RO_OPTS" shared_postgres psql -X -U postgres -d erpx -v ON_ERROR_STOP=1 "$@"; }

PASS=0; WARN=0; FAIL=0
say() { printf '  [%s] %s\n' "$1" "$2"; case "$1" in PASS) PASS=$((PASS+1));; WARN) WARN=$((WARN+1));; FAIL) FAIL=$((FAIL+1));; esac; }

if [ "$DRY_RUN" = 1 ]; then
  echo "DRY RUN: this preflight only reads. It would run: df, du, date, head, systemctl is-active / list-timers, docker inspect, one docker exec (alembic heads),"
  echo "git rev-parse and git status (no locks), aws s3 ls s3://$BUCKET/daily/, and read-only psql sessions (PGOPTIONS: $RO_OPTS) against shared_postgres/erpx."
  exit 0
fi

echo "== A. database revision and what is running"
date -u
REV=$(q -tA -c "select version_num from alembic_version" 2>&1 | tail -1)
echo "production database revision (alembic_version): $REV"
if [[ "$REV" =~ ^[0-9]{4}$ ]]; then N=$((10#$REV)); else N=-1; fi
if   [ "$N" -lt 0 ];   then say FAIL "could not read alembic_version ($REV): is shared_postgres reachable?"
elif [ "$N" -gt 107 ]; then say FAIL "the database is at $REV, AHEAD of this release (0107): another release is in place; stop and find out which"
elif [ "$N" -eq 107 ]; then say WARN "already at 0107: this release has been applied (or a previous attempt did)"
elif [ "$N" -ge 104 ]; then say PASS "at $REV: the release applies 0107 (0104-0106 are already in; read report F anyway)"
else say WARN "at $REV, BELOW 0104: deploying also applies every revision up to 0107, including 0104-0106. Read reports F and G, and decide whether those were meant to ship in this window"
fi
echo "head the RUNNING api image knows: $(docker exec -e PYTHONDONTWRITEBYTECODE=1 erpx_api alembic heads 2>&1 | tail -1)"   # reads the migration files only; it does not touch the database
echo "running images (rollback targets):"
for c in erpx_api erpx_celery_worker erpx_celery_beat erpx_web erpx_student_portal erpx_trainer_portal; do
  docker inspect -f '  {{.Name}} image={{.Config.Image}} id={{.Image}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$c" 2>&1
done
if [ "$(docker inspect -f '{{.State.Health.Status}}' erpx_api 2>/dev/null)" = healthy ]; then say PASS "erpx_api is healthy"; else say FAIL "erpx_api is not healthy before the release"; fi
if [ -d $ERPX_DIR/.git ]; then
  echo "source checkout $ERPX_DIR: HEAD $(git -C "$ERPX_DIR" rev-parse HEAD 2>&1)"
  if [ -z "$(git -C "$ERPX_DIR" --no-optional-locks status --porcelain --untracked-files=no 2>&1)" ]; then say PASS "/opt/erpx has no tracked local changes (a fast-forward will work)"; else say FAIL "/opt/erpx has tracked local changes"; fi
else
  say FAIL "/opt/erpx is not a git checkout"
fi

echo; echo "== B. disk space"
df -h / | tail -1
AVAIL=$(df -B1 --output=avail / | tail -1 | tr -d ' ')
DBSIZE=$(q -tA -c "select pg_database_size(current_database())" 2>/dev/null | tail -1)
echo "free: $((AVAIL/1024/1024)) MiB   database size: $(( ${DBSIZE:-0}/1024/1024 )) MiB   pre-release folder: $(du -sh $PRE_DIR 2>/dev/null | cut -f1)"
NEED=$(( ${DBSIZE:-0} * 2 )); [ "$NEED" -lt 4000000000 ] && NEED=4000000000
if [ "$AVAIL" -ge "$NEED" ]; then say PASS "free disk $((AVAIL/1024/1024)) MiB >= $((NEED/1024/1024)) MiB (the larger of 4 GB and twice the database, for the pre-migration dump plus image builds)"; else say FAIL "free disk $((AVAIL/1024/1024)) MiB < $((NEED/1024/1024)) MiB needed"; fi

echo; echo "== C. off-server backup"
echo "timer: $(systemctl is-active offsite-backup.timer 2>&1)"; systemctl list-timers --all 2>/dev/null | grep -E 'offsite|NEXT' | cut -c1-170
echo "last_status.json:"; head -c 600 /opt/backups/offsite/last_status.json 2>&1; echo
[ "$(systemctl is-active offsite-backup.timer 2>/dev/null)" = active ] && say PASS "offsite-backup.timer is active" || say FAIL "offsite-backup.timer is not active"
NEWEST=$(aws s3 ls "s3://$BUCKET/daily/" 2>/dev/null | awk '$1=="PRE"{print $2}' | tr -d '/' | sort | tail -1)
if [ -z "$NEWEST" ]; then
  say FAIL "could not list s3://$BUCKET/daily/ (no instance role, no network, or no backups)"
else
  echo "newest day folder: $NEWEST"; aws s3 ls "s3://$BUCKET/daily/$NEWEST/" 2>&1 | sed 's/^/    /'
  AGE_H=$(( ( $(date -u +%s) - $(date -u -d "$NEWEST 03:30" +%s) ) / 3600 ))
  [ "$AGE_H" -le 27 ] && say PASS "newest off-server backup is $AGE_H h old (limit 27 h)" || say FAIL "newest off-server backup is $AGE_H h old (limit 27 h)"
  aws s3 ls "s3://$BUCKET/daily/$NEWEST/" 2>/dev/null | grep -q SHA256SUMS && say PASS "SHA256SUMS present (the backup finished and was verified)" || say FAIL "SHA256SUMS missing: that day's backup did not finish"
  aws s3 ls "s3://$BUCKET/daily/$NEWEST/" 2>/dev/null | grep -q manifest.json && say PASS "manifest.json present" || say WARN "manifest.json missing"
fi
echo "newest in-app backup records (informational; the in-app dump is not the recovery copy):"
q -tA -F ' | ' -c "select left(id::text,8), status, coalesce(storage_key,'(cleared)'), size_bytes, to_char(completed_at,'YYYY-MM-DD HH24:MI') from backup_jobs order by started_at desc limit 4" 2>&1 | sed 's/^/    /'

echo; echo "== D. long-running transactions and lock waits (the migration needs brief locks: run it when this is quiet)"
q -c "select pid, state, now()-xact_start as open_for, left(query,70) as query from pg_stat_activity where xact_start is not null and now()-xact_start > interval '1 minute' and pid <> pg_backend_pid() order by xact_start" 2>&1
LONG=$(q -tA -c "select count(*) from pg_stat_activity where xact_start is not null and now()-xact_start > interval '1 minute' and pid <> pg_backend_pid()" 2>/dev/null | tail -1)
VERYLONG=$(q -tA -c "select count(*) from pg_stat_activity where xact_start is not null and now()-xact_start > interval '10 minutes' and pid <> pg_backend_pid()" 2>/dev/null | tail -1)
WAITING=$(q -tA -c "select count(*) from pg_locks where not granted" 2>/dev/null | tail -1)
IDLE=$(q -tA -c "select count(*) from pg_stat_activity where state = 'idle in transaction' and pid <> pg_backend_pid()" 2>/dev/null | tail -1)
echo "open > 1 min: $LONG   open > 10 min: $VERYLONG   idle in transaction: $IDLE   waiting for a lock: $WAITING"
[ "${VERYLONG:-1}" = 0 ] && say PASS "no transaction open longer than 10 minutes" || say FAIL "a transaction has been open longer than 10 minutes (find out what it is before migrating)"
[ "${LONG:-1}" = 0 ] && say PASS "no transaction open longer than 1 minute" || say WARN "a transaction is open longer than 1 minute (re-run just before migrating)"
[ "${WAITING:-1}" = 0 ] && say PASS "nothing waiting for a lock" || say WARN "something is waiting for a lock"

echo; echo "== E. how many rows migration 0107 will touch, and exam behaviour that changes with this release"
q -tA -F ' | ' -c "select 'workshop_exam_attendees', count(*) from workshop_exam_attendees union all select 'lms_assessments', count(*) from lms_assessments union all select 'lms_assessment_attempts', count(*) from lms_assessment_attempts union all select 'course_resources', count(*) from course_resources union all select 'exam_practicals', count(*) from exam_practicals union all select 'exam_vivas', count(*) from exam_vivas union all select 'lms_discussion_threads', count(*) from lms_discussion_threads" 2>&1 | sed 's/^/    /'
echo "OPEN internship exams (after this release their public sign-up link refuses new people: students use the personal links the internship team assigns). Empty = nothing is affected:"
q -c "select id, title, status::text as status, (select count(*) from workshop_exam_attendees a where a.exam_id = workshop_exams.id) as attendees from workshop_exams where internship_id is not null and award is null and status::text = 'open' order by title" 2>&1 | sed 's/^/    /'

echo "exams being taken right now (the api restart drops requests for a few seconds; pick a time when this is 0):"
INPROG=$(q -tA -c "select (select count(*) from workshop_exam_attendees where started_at is not null and submitted_at is null and started_at > now() - interval '6 hours') + (select count(*) from lms_assessment_attempts where status::text = 'in_progress' and started_at > now() - interval '6 hours')" 2>/dev/null | tail -1)
echo "    attempts started in the last 6 hours and not submitted: ${INPROG:-?}"
[ "${INPROG:-1}" = 0 ] && say PASS "no exam or quiz attempt is in progress" || say WARN "${INPROG:-?} exam/quiz attempt(s) in progress: deploy later, or accept a brief interruption"

echo; echo "== F. data reports: migrations 0104-0106 (ops/preflight/0104_0106_lms_access_ambiguity.sql) -- an empty result is good news"
q <<'SQL_EOF'
-- READ-ONLY preflight for migrations 0104 and 0106 (internship LMS access).
--
-- Run it on the production database BEFORE applying 0104..0106 (it also works afterwards). It changes nothing: every statement is a
-- SELECT inside a READ ONLY transaction, so the database itself refuses a write. It returns ids and titles only (no names, emails or
-- phone numbers).
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f ops/preflight/0104_0106_lms_access_ambiguity.sql
--
-- WHY. Migration 0104 adds our_internship_selections.lms_course_id, "the course this student was given access to", and fills it for
-- students who already have or had LMS access with the internship's CURRENT course. Before 0104 an administrator could change an
-- internship's course at any time (even with students enrolled), so for an internship that was relinked after access was granted that
-- value is the NEW course, not the one the student was enrolled in. Nothing in the database records the old course on the selection,
-- so the migration does not guess: it copies the only value there is, which is exactly what revoking has always used. The records
-- below are the ones where that value may be wrong. A person decides what, if anything, to correct (the migrations never do).
--
-- Migration 0106 adds lms_enrolment_preexisting (false for every existing row). Section 4 lists granted selections whose enrolment is
-- older than the grant: for those, revoking the internship's access would withdraw an enrolment the student may have held on their own.
--
-- Reading the results: sections 1-3 are about relinked courses, section 4 about independent enrolments. An empty result is good news.
-- Section 3 and 4 can contain false positives (a re-granted student, an enrolment made by the first of two grants), so treat them as
-- a list to look at, not a list to fix.

BEGIN TRANSACTION READ ONLY;

-- 1. Every time an internship's LMS course was changed AWAY from a course (relinked to another, or cleared), from the audit trail:
--    old and new course, and when. (The first time a course is chosen is not a relink and is not listed.)
SELECT i.organization_id, i.id AS internship_id, i.title AS internship, a.created_at AS changed_at,
       a.changes -> 'lms_course_id' ->> 'old' AS old_course_id, a.changes -> 'lms_course_id' ->> 'new' AS new_course_id,
       i.lms_course_id AS current_course_id
FROM audit_logs a
JOIN our_internships i ON i.id = a.entity_id
WHERE a.entity_type = 'our_internships' AND a.action = 'update' AND a.changes -> 'lms_course_id' ->> 'old' IS NOT NULL
ORDER BY i.title, a.created_at;

-- 2. Selections with LMS access (granted or since revoked) whose internship was relinked AFTER the access was last granted:
--    the 0104 backfill points them at the new course, which is probably not the one they were enrolled in. Review these first.
SELECT i.organization_id, i.id AS internship_id, i.title AS internship, s.id AS selection_id, s.lms_status::text AS lms_status,
       s.lms_student_id, s.lms_granted_at, r.changed_at AS course_changed_at, r.old_course_id, r.new_course_id,
       i.lms_course_id AS current_course_id
FROM our_internship_selections s
JOIN our_internships i ON i.id = s.internship_id
JOIN (
    SELECT a.entity_id AS internship_id, a.created_at AS changed_at,
           a.changes -> 'lms_course_id' ->> 'old' AS old_course_id, a.changes -> 'lms_course_id' ->> 'new' AS new_course_id
    FROM audit_logs a
    WHERE a.entity_type = 'our_internships' AND a.action = 'update' AND a.changes -> 'lms_course_id' ->> 'old' IS NOT NULL
) r ON r.internship_id = i.id
WHERE s.lms_status IN ('granted', 'revoked') AND (s.lms_granted_at IS NULL OR r.changed_at > s.lms_granted_at)
ORDER BY i.title, s.id, r.changed_at;

-- 3. Students whose access is GRANTED but who hold no live enrolment in the internship's current course (the backfill would record a
--    course they are not in), and granted/revoked selections on an internship that now has no course at all (the backfill leaves
--    them empty).
SELECT i.organization_id, i.id AS internship_id, i.title AS internship, s.id AS selection_id, s.lms_status::text AS lms_status,
       s.lms_student_id, i.lms_course_id AS current_course_id,
       CASE WHEN i.lms_course_id IS NULL THEN 'internship has no course now' ELSE 'no live enrolment in the current course' END AS why
FROM our_internship_selections s
JOIN our_internships i ON i.id = s.internship_id
WHERE (
        s.lms_status = 'granted' AND s.lms_student_id IS NOT NULL AND i.lms_course_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM lms_enrollments e
            WHERE e.student_id = s.lms_student_id AND e.course_id = i.lms_course_id AND e.status IN ('active', 'completed')
        )
      )
   OR (s.lms_status IN ('granted', 'revoked') AND i.lms_course_id IS NULL)
ORDER BY i.title, s.id;

-- 4. Granted selections whose enrolment in the internship's course is OLDER than the grant (by more than a minute): the student may
--    have been enrolled on their own (an administrator, a purchase) before the internship gave them access. After 0106 a NEW grant
--    remembers this by itself; for these existing rows it stays "false" (revoking withdraws the enrolment, as before) unless a person
--    decides otherwise. May include students who were re-granted, or who joined through the first of two internships.
SELECT i.organization_id, i.id AS internship_id, i.title AS internship, s.id AS selection_id, s.lms_student_id,
       e.id AS enrolment_id, e.status::text AS enrolment_status, e.created_at AS enrolment_created_at, s.lms_granted_at
FROM our_internship_selections s
JOIN our_internships i ON i.id = s.internship_id
JOIN lms_enrollments e ON e.student_id = s.lms_student_id AND e.course_id = i.lms_course_id
WHERE s.lms_status = 'granted' AND s.lms_granted_at IS NOT NULL
  AND e.created_at < s.lms_granted_at - interval '1 minute'
ORDER BY i.title, s.id;

ROLLBACK;
SQL_EOF

echo; echo "== G. data report: migration 0107 (ops/preflight/0107_learning_integration.sql) -- an empty result is good news"
q <<'SQL_EOF'
-- READ-ONLY preflight for migration 0107 (Learning integration).
--
-- Run it on the production database BEFORE applying 0107 (it also works afterwards: it only reads columns that exist before the
-- migration). It changes nothing: every statement is a SELECT inside a READ ONLY transaction, so the database itself refuses a write.
-- It returns ids, titles and counts only (no names, emails or phone numbers).
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f ops/preflight/0107_learning_integration.sql
--
-- WHY. Migration 0107 adds workshop_exam_attendees.selection_id, the stable link from a person on an internship's exam to the student
-- (selection) it was assigned for. Until now that link was only an e-mail match. The migration fills selection_id ONLY where exactly one
-- selection of the exam's internship matches the attendee's e-mail; it never guesses between two. From the release on, a link to an
-- internship exam works only while that student's LMS access on the internship is granted, so the lists below are the people for whom
-- that will change. A person decides what, if anything, to correct (the migration never does).
--
-- Reading the results: an empty result is good news.

BEGIN TRANSACTION READ ONLY;

-- 1. Exam attendees the backfill will NOT link to a selection, because no selection or more than one selection of the internship
--    matches their e-mail. Per exam: how many, and why. These keep working only while the e-mail still matches exactly one student
--    with granted access.
SELECT e.organization_id, e.id AS exam_id, e.title AS exam, e.internship_id,
       count(*) FILTER (WHERE m.matches = 0) AS attendees_matching_no_selection,
       count(*) FILTER (WHERE m.matches > 1) AS attendees_matching_several_selections
FROM workshop_exams e
JOIN (
    SELECT a.id AS attendee_id, a.exam_id,
           (SELECT count(*) FROM our_internship_selections s
              JOIN institution_students p ON p.id = s.student_id
             WHERE s.internship_id = x.internship_id AND lower(btrim(p.email)) = lower(btrim(a.email))) AS matches
    FROM workshop_exam_attendees a
    JOIN workshop_exams x ON x.id = a.exam_id AND x.internship_id IS NOT NULL AND x.award IS NULL
    WHERE a.certificate_only = false
) m ON m.exam_id = e.id
WHERE m.matches <> 1
GROUP BY e.organization_id, e.id, e.title, e.internship_id
ORDER BY e.title;

-- 2. Attendees of an internship exam whose student does NOT currently hold granted LMS access on that internship (revoked, or never
--    granted). Their personal exam link stops working with the release. (Their results, and the marked history, are kept.)
SELECT e.organization_id, e.id AS exam_id, e.title AS exam, e.internship_id, s.lms_status::text AS lms_status, count(DISTINCT a.id) AS attendees
FROM workshop_exams e
JOIN workshop_exam_attendees a ON a.exam_id = e.id AND a.certificate_only = false
JOIN our_internship_selections s ON s.internship_id = e.internship_id
JOIN institution_students p ON p.id = s.student_id AND lower(btrim(p.email)) = lower(btrim(a.email))
WHERE e.internship_id IS NOT NULL AND e.award IS NULL AND s.lms_status <> 'granted'
  AND NOT EXISTS (
      SELECT 1 FROM our_internship_selections g
      JOIN institution_students gp ON gp.id = g.student_id AND lower(btrim(gp.email)) = lower(btrim(a.email))
      WHERE g.internship_id = e.internship_id AND g.lms_status = 'granted')
GROUP BY e.organization_id, e.id, e.title, e.internship_id, s.lms_status
ORDER BY e.title;

-- 3. Two or more selected students of one internship sharing an e-mail address (the backfill cannot tell them apart, so their exam
--    attendees are listed in section 1 as "matching several"). One row per internship and shared address; the address is not shown.
SELECT s.organization_id, s.internship_id, i.title AS internship, count(*) AS students_sharing_the_address
FROM our_internship_selections s
JOIN our_internships i ON i.id = s.internship_id
JOIN institution_students p ON p.id = s.student_id
WHERE p.email IS NOT NULL AND btrim(p.email) <> ''
GROUP BY s.organization_id, s.internship_id, i.title, lower(btrim(p.email))
HAVING count(*) > 1
ORDER BY i.title;

-- 4. Assessments that already have attempts. They had no questions before this release, so their attempts hold hand-recorded scores;
--    those attempts keep their score exactly as it is and are never re-scored. Listed so staff know which assessments stay manual.
SELECT c.organization_id, a.course_id, a.id AS assessment_id, a.title AS assessment, count(t.id) AS recorded_attempts
FROM lms_assessments a
JOIN courses c ON c.id = a.course_id
JOIN lms_assessment_attempts t ON t.assessment_id = a.id
GROUP BY c.organization_id, a.course_id, a.id, a.title
ORDER BY a.title;

ROLLBACK;
SQL_EOF

echo; echo "== SUMMARY: PASS=$PASS WARN=$WARN FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then echo "RESULT: NO-GO (fix every FAIL line above, then run this preflight again)"; else echo "RESULT: no blocker found by the automatic checks (read the WARN lines and the two data reports before you approve)"; fi
echo "== done (nothing was changed)"
