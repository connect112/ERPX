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
