-- Read-only facts and checks for the automatic-reconciliation acceptance test (./staging.sh recon report). Selects only;
-- no secrets (the webhook table keeps no signature or body). One "key=value" line per fact or check.
-- Variables (all required, may be empty):  app   application reference (e.g. ERPX-INT-2026-000009), or '' for the latest
--   Cashfree order created since the test mode went on;  since   when the test mode went on (UTC timestamp);
--   task_ok  UTC timestamp of the worker's "reconcile_payments succeeded ... 'confirmed': N>=1" log line, or ''.
\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on
\pset fieldsep '='
\pset footer off
WITH target AS (
  SELECT o.*, a.reference FROM internship_payment_orders o JOIN internship_onboarding_applications a ON a.id = o.application_id
  WHERE o.method = 'cashfree'
    AND ((:'app' <> '' AND a.reference = :'app') OR (:'app' = '' AND o.created_at >= NULLIF(:'since', '')::timestamptz))
  ORDER BY o.created_at DESC LIMIT 1
), ev AS (
  SELECT e.created_at, e.detail->>'source' AS source FROM internship_onboarding_events e
  WHERE e.application_id = (SELECT application_id FROM target) AND e.event = 'payment_confirmed'
), f AS (
  SELECT
    (SELECT reference FROM target) AS app,
    (SELECT merchant_order_id FROM target) AS ord,
    (SELECT status FROM target) AS ostatus,
    (SELECT created_at FROM target) AS ocreated,
    (SELECT last_checked_at FROM target) AS olast,
    (SELECT paid_at FROM target) AS opaid,
    (SELECT count(*) FROM internship_payment_transactions x WHERE x.application_id = (SELECT application_id FROM target)
       AND x.kind = 'payment' AND x.provider = 'cashfree' AND x.status = 'confirmed') AS npay,
    (SELECT max(x.provider_payment_id) FROM internship_payment_transactions x WHERE x.application_id = (SELECT application_id FROM target)
       AND x.kind = 'payment' AND x.provider = 'cashfree' AND x.status = 'confirmed') AS payid,
    (SELECT count(*) FROM internship_financial_documents d WHERE d.application_id = (SELECT application_id FROM target) AND d.kind = 'receipt') AS ndoc,
    (SELECT max(d.number) FROM internship_financial_documents d WHERE d.application_id = (SELECT application_id FROM target) AND d.kind = 'receipt') AS docno,
    (SELECT count(*) FROM ev) AS nev,
    (SELECT min(created_at) FROM ev) AS evat,
    (SELECT min(source) FROM ev) AS evsrc,
    (SELECT count(*) FROM internship_payment_webhooks w WHERE w.merchant_order_id = (SELECT merchant_order_id FROM target)) AS nhook,
    NULLIF(:'since', '')::timestamptz AS since,
    NULLIF(:'task_ok', '')::timestamptz AS taskok
)
SELECT 'fact.application', coalesce(app, 'NONE') FROM f UNION ALL
SELECT 'fact.order', coalesce(ord, 'NONE') FROM f UNION ALL
SELECT 'fact.order_status', coalesce(ostatus, 'NONE') FROM f UNION ALL
SELECT 'fact.order_created_at', coalesce(to_char(ocreated AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'NONE') FROM f UNION ALL
SELECT 'fact.order_last_checked_at', coalesce(to_char(olast AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'NONE') FROM f UNION ALL
SELECT 'fact.order_paid_at', coalesce(to_char(opaid AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'NONE') FROM f UNION ALL
SELECT 'fact.cashfree_payment_id', coalesce(payid, 'NONE') FROM f UNION ALL
SELECT 'fact.confirmed_payments', npay::text FROM f UNION ALL
SELECT 'fact.receipts', ndoc::text FROM f UNION ALL
SELECT 'fact.receipt_number', coalesce(docno, 'NONE') FROM f UNION ALL
SELECT 'fact.confirmed_events', nev::text FROM f UNION ALL
SELECT 'fact.confirmed_event_at', coalesce(to_char(evat AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'NONE') FROM f UNION ALL
SELECT 'fact.confirmed_event_source', coalesce(evsrc, 'NONE') FROM f UNION ALL
SELECT 'fact.notifications_that_reached_erpx', nhook::text FROM f UNION ALL
-- checks (each must be true)
SELECT 'check.paid_by_one_payment_one_receipt_one_event', (ostatus = 'paid' AND npay = 1 AND ndoc = 1 AND nev = 1)::text FROM f UNION ALL
SELECT 'check.test_mode_was_on_before_checkout', coalesce(since <= ocreated, false)::text FROM f UNION ALL
SELECT 'check.confirmed_at_least_10_minutes_after_checkout', coalesce(evat - ocreated >= interval '10 minutes', false)::text FROM f UNION ALL
SELECT 'check.confirmation_source_is_status_check', coalesce(evsrc = 'status check', false)::text FROM f UNION ALL
SELECT 'check.order_last_checked_at_matches_confirmation', coalesce(abs(extract(epoch FROM (olast - evat))) <= 120, false)::text FROM f UNION ALL
SELECT 'check.confirmation_inside_scheduled_task_run', coalesce(abs(extract(epoch FROM (taskok - evat))) <= 120, false)::text FROM f UNION ALL
SELECT 'check.no_notification_reached_erpx', (nhook = 0)::text FROM f UNION ALL
-- the integrity checks of ./staging.sh evidence (each must be 0)
SELECT 'integrity.payments_recorded_twice', count(*)::text FROM (
  SELECT provider_payment_id FROM internship_payment_transactions
  WHERE provider = 'cashfree' AND kind = 'payment' AND provider_payment_id IS NOT NULL
  GROUP BY provider_payment_id HAVING count(*) > 1) x UNION ALL
SELECT 'integrity.documents_issued_twice', count(*)::text FROM (
  SELECT transaction_id FROM internship_financial_documents GROUP BY transaction_id HAVING count(*) > 1) x UNION ALL
SELECT 'integrity.confirmed_without_document', count(*)::text FROM internship_payment_transactions t
  LEFT JOIN internship_financial_documents d ON d.transaction_id = t.id
  WHERE t.status = 'confirmed' AND t.kind IN ('payment', 'refund') AND d.id IS NULL UNION ALL
SELECT 'integrity.refund_adjustment_mismatches', count(*)::text FROM internship_payment_transactions w
  WHERE w.kind = 'waiver' AND w.note = 'refund_adjustment' AND NOT EXISTS (
    SELECT 1 FROM internship_payment_transactions r WHERE r.kind = 'refund' AND r.status = 'confirmed' AND r.refund_of_id = w.refund_of_id) UNION ALL
SELECT 'integrity.accounting_journal_entries', count(*)::text FROM accounting_journal_entries;
