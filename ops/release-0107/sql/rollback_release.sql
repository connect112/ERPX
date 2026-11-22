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
