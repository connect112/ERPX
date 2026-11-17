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
