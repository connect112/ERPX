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
