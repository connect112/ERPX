-- Read-only evidence for the Cashfree sandbox acceptance (./staging.sh evidence). Selects only; no secrets: the
-- webhook table keeps a hash, type, order id and outcome, never a signature or a body.
\pset footer off
\echo '== payment orders'
SELECT o.merchant_order_id, o.amount, o.status, o.created_at, o.paid_at, o.last_checked_at, a.reference
FROM internship_payment_orders o JOIN internship_onboarding_applications a ON a.id = o.application_id
ORDER BY o.created_at;

\echo '== ledger (payments, refunds, charges, waivers)'
SELECT a.reference, t.kind, t.method, t.status, t.amount, t.provider_payment_id, t.provider_refund_id, t.note, t.created_at
FROM internship_payment_transactions t JOIN internship_onboarding_applications a ON a.id = t.application_id
ORDER BY a.reference, t.created_at;

\echo '== net per student (paid - refunded) and adjustments'
SELECT a.reference,
       sum(t.amount) FILTER (WHERE t.kind = 'payment' AND t.status = 'confirmed') AS paid,
       sum(t.amount) FILTER (WHERE t.kind = 'refund' AND t.status = 'confirmed') AS refunded,
       sum(t.amount) FILTER (WHERE t.kind = 'waiver' AND t.status = 'confirmed') AS waived,
       sum(t.amount) FILTER (WHERE t.kind = 'charge' AND t.status = 'confirmed') AS charged
FROM internship_payment_transactions t JOIN internship_onboarding_applications a ON a.id = t.application_id
GROUP BY a.reference ORDER BY a.reference;

\echo '== receipts and credit notes (one per confirmed payment/refund; email sent once)'
SELECT d.number, d.kind, d.amount, d.email_status, d.email_attempts, d.emailed_at, d.issued_at
FROM internship_financial_documents d ORDER BY d.issued_at;

\echo '== CHECKS: each line must show 0'
SELECT 'payments recorded twice for one Cashfree payment id' AS check, count(*) AS problems FROM (
  SELECT provider_payment_id FROM internship_payment_transactions
  WHERE provider = 'cashfree' AND kind = 'payment' AND provider_payment_id IS NOT NULL
  GROUP BY provider_payment_id HAVING count(*) > 1) x
UNION ALL
SELECT 'documents issued twice for one transaction', count(*) FROM (
  SELECT transaction_id FROM internship_financial_documents GROUP BY transaction_id HAVING count(*) > 1) x
UNION ALL
SELECT 'confirmed payments/refunds without a document', count(*) FROM internship_payment_transactions t
  LEFT JOIN internship_financial_documents d ON d.transaction_id = t.id
  WHERE t.status = 'confirmed' AND t.kind IN ('payment', 'refund') AND d.id IS NULL
UNION ALL
SELECT 'refund adjustments not matching a confirmed refund', count(*) FROM internship_payment_transactions w
  WHERE w.kind = 'waiver' AND w.note = 'refund_adjustment' AND NOT EXISTS (
    SELECT 1 FROM internship_payment_transactions r WHERE r.kind = 'refund' AND r.status = 'confirmed' AND r.refund_of_id = w.refund_of_id)
UNION ALL
SELECT 'accounting journal entries (onboarding never posts any)', count(*) FROM accounting_journal_entries;

\echo '== Cashfree notifications received (no signatures or bodies are stored)'
SELECT w.created_at, w.event_type, w.merchant_order_id, w.signature_valid, w.outcome
FROM internship_payment_webhooks w ORDER BY w.created_at;

\echo '== timeline events by type'
SELECT e.event, count(*) FROM internship_onboarding_events e
WHERE e.event IN ('checkout_started', 'payment_confirmed', 'payment_failed', 'payment_mismatch', 'document_issued',
                  'refund_requested', 'refund_completed', 'refund_failed', 'gateway_auto_refund')
GROUP BY e.event ORDER BY e.event;
