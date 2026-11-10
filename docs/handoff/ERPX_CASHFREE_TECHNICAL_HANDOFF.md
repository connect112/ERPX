# ERPX Cashfree: technical handoff

State described: `master` `86e4a86` (adapter as merged in PR #161) **plus** PR #163 head `d96b97606c9bbf0d2eedc1414844cbc4daa8531d`
(reconciliation fix, auto-refund handling, seed fix, Celery pins). Line numbers below are from the PR #163 branch.
Provenance tags as in `ERPX_COMPLETE_DEVELOPMENT_HISTORY.md`: GIT = verified in code, OWNER = reported by the owner, CLOUD = observed in the Cloud container, UNVERIFIED = assumption.

**Nothing here is deployed by the Cloud session. Cashfree is off in production by default and must stay off until the owner says otherwise.**

## 1. Where the code is

| Concern | File | Notes |
|---|---|---|
| Provider interface and DTOs | `modules/internship_onboarding/providers/base.py` | `PaymentProvider` (ABC), `ProviderError`, `CreatedOrder`, `ProviderPayment`, `ProviderRefund`, `WebhookEvent` (PR #163 adds `auto_refund_payment_id`, `auto_refund_amount`). |
| Cashfree adapter | `modules/internship_onboarding/providers/cashfree.py` | `CashfreeProvider`: `from_settings`, `_headers`, `_request`, `create_order`, `order_payments`, `_payment`, `_refund`, `create_refund`, `refund_status`, `verify_webhook`, `parse_webhook`. |
| Provider lookup | `modules/internship_onboarding/providers/__init__.py` | `get_provider("cashfree")`. |
| Payment logic | `modules/internship_onboarding/payments.py` | `PaymentService` and `RefundService` (below). |
| Scheduled reconciliation | `modules/internship_onboarding/tasks.py` | `_reconcile()`, Celery task `internship_onboarding.reconcile_payments`. |
| Beat schedule | `apps/api/app/core/celery_app.py` | `"internship-onboarding-reconcile-payments"`: `crontab(minute="*/15")` (UTC). |
| HTTP routes | `modules/internship_onboarding/routes.py` | `public_router`: `POST /internship-onboarding/payments/checkout`, `POST /internship-onboarding/payments/refresh`, `GET /internship-onboarding/financial-documents/{id}`, `POST /payments/cashfree/webhook` (full path `/api/v1/public/payments/cashfree/webhook`). |
| Models | `modules/internship_onboarding/models.py` | `PaymentOrder`, `PaymentTransaction` (the ledger), `PaymentWebhookEvent`, `FinancialDocument`, `OnboardingApplication`. |
| Receipts / invoices / credit notes | `modules/internship_onboarding/financial.py` | `issue`, `issue_safely`, `render_pdf`, `kind_for`, `_send`, `send_document_task`, `enqueue_email`, `missing`. Email Studio template `internship_onboarding_receipt`. |
| Ledger maths | `modules/internship_onboarding/ledger.py`, `fees.py` | totals paid / refunded / payable / balance. |
| Settings | `apps/api/app/core/config.py` lines 107 to 117 | `CASHFREE_*` (below). |
| Migrations | `apps/api/alembic/versions/0098_internship_onboarding.py`, `0099_internship_payments.py`, `0100_internship_financial_documents.py` | Merged. PR #163 adds none. |
| Staging kit (PR #163 only) | `ops/staging-cashfree/` | Mac Compose stack, `staging.sh`, `preflight.sh`, `recon.sql`, `evidence.sql`, `seed_synthetic.py`, `gate-templates/`, shell tests. |
| Tests | `tests/api/test_internship_onboarding_cashfree_attempts.py` (18, PR #163), plus the existing `tests/api/test_internship_onboarding*.py` (76 in the Cloud run) and `tests/unit` Cashfree/fee tests; opt-in sandbox tests (6, skipped by default). |

## 2. Configuration (names only; values are secrets and are never in the repository)

| Setting | Default | Meaning |
|---|---|---|
| `CASHFREE_ENABLED` | `false` | Master switch. If false, `CashfreeProvider.from_settings` raises `ProviderError("Online payment is not switched on…")`, the webhook answers 503, `_reconcile()` returns `{checked:0, confirmed:0}`. |
| `CASHFREE_ENV` | `sandbox` | `sandbox` → `https://sandbox.cashfree.com/pg`; `production` → `https://api.cashfree.com/pg` (`BASE_URLS`). |
| `CASHFREE_ALLOW_PRODUCTION` | `false` | Three-flag guard: production is refused (`"Live Cashfree payments are not authorised on this server."`) unless this is true as well. |
| `CASHFREE_APP_ID`, `CASHFREE_SECRET_KEY` | empty | From the environment only. Empty is refused. Never logged: `CashfreeProvider.__repr__` hides the secret. |
| `CASHFREE_API_VERSION` | `2025-01-01` | Sent as `x-api-version`; the webhook version in the Cashfree dashboard should match. `2026-01-01` was **not** tested. |
| `CASHFREE_ORDER_MINUTES` | `30` | Order expiry (minimum 15 is enforced in `start_checkout`). |
| `CASHFREE_WEBHOOK_MAX_AGE_HOURS` | `72` | Replay window for webhook timestamps. |

Authentication to Cashfree: request headers `x-client-id` (App ID), `x-client-secret` (Secret Key), `x-api-version`, JSON content type (`_headers`). Timeouts 15 s, connect 5 s (`TIMEOUT`).

**Production wiring (GIT, inferred):** `docker-compose.prod.yml` passes no `CASHFREE_*` variables to the containers (only names listed in `x-backend-env` reach them), so enabling Cashfree in production needs a separate, owner-approved change. UNVERIFIED: the actual production `/opt/erpx/.env` was never inspected by the Cloud session.

## 3. Flow, step by step (GIT)

### 3.1 Creating an order and checkout (`PaymentService.start_checkout`, payments.py ~285)
1. Cashfree must be an enabled method of the internship's fee settings; the amount is computed server-side by `_payable_now` (from the internship's configured fee snapshot, never from the browser).
2. `get_provider("cashfree")`; `ProviderError` becomes `ServiceUnavailableError`.
3. The application row is locked (`SELECT … FOR UPDATE`). An existing `active` Cashfree order for the same amount that expires in more than 5 minutes and has a `payment_session_id` is **reused** (the student gets the same checkout).
4. Otherwise a new `PaymentOrder` is created with `merchant_order_id = "ERPXI" + 24 hex characters`, expiry now + max(15, `CASHFREE_ORDER_MINUTES`) minutes, status `created`; `provider.create_order` posts `/orders` with `order_id`, `order_amount`, `order_currency`, `customer_details` (customer id = application reference; a 10-digit mobile number is required: `_phone`), `order_meta.return_url = FRONTEND_URL + /internship-onboarding?order=<merchant_order_id>`, `order_expiry_time`, `order_note`.
5. The reply is checked: same `order_id`, a `payment_session_id`, same amount and currency, otherwise `ProviderError`. On a gateway error the local order becomes `failed`.
6. The order becomes `active`; a `checkout_started` timeline event is written; the browser receives `payment_session_id`, the environment and the order id. The return URL is fixed at order creation (relevant to the stuck-return-page analysis, section 6).

### 3.2 Payment attempts and retries
A Cashfree **order** can receive several payment **attempts** until it expires. ERPX maps attempt statuses (`providers/cashfree.py` `STATUS`): `SUCCESS` → success; `FAILED`, `USER_DROPPED`, `CANCELLED`, `VOID` → failed; everything else (e.g. `PENDING`, `NOT_ATTEMPTED`) → pending. Only a verified `SUCCESS` for the order's **exact amount and currency** confirms a payment (`apply_gateway_payment`); a success of another amount or currency writes a `payment_mismatch` event and is left for staff.
A failed attempt sets a local `active` order to `failed`; the student-facing state is derived from that, and a student can start a **fresh order** (a new `merchant_order_id`), which is how the accepted "failed payment, retry creates a new order" behaviour works.

### 3.3 Webhook (`PaymentService.handle_webhook`, payments.py ~406; route `cashfree_webhook`)
1. Body larger than 64 KiB → 413. Rate limit 300/minute.
2. Provider not configured → 503 `"not configured"`.
3. **Signature** (`verify_webhook`): headers `x-webhook-signature` and `x-webhook-timestamp` are required; expected = base64(HMAC-SHA256(secret, timestamp + raw_body)); compared with `hmac.compare_digest`; the timestamp (seconds or milliseconds) must be at most 5 minutes in the future and at most `CASHFREE_WEBHOOK_MAX_AGE_HOURS` old. Failure → 401 `"invalid signature"`, nothing processed.
4. **Duplicates:** `PaymentWebhookEvent.event_hash = sha256(raw_body)`; if already `processed_at` → 200 `"duplicate"`. A re-wrapped copy with a different body falls through to step 6 and is stopped by the payment-level idempotency.
5. `parse_webhook`: `AUTO_REFUND*` types are read separately (their body lacks the usual order block); refunds carry `data.refund`; otherwise `data.order.order_id` and `data.payment`. Unreadable → 400.
6. The order is looked up by `merchant_order_id` with `FOR UPDATE`. `AUTO_REFUND*` → `report_auto_refund` (below). Unknown order → 200 `"unknown order"`. Refund events → `apply_gateway_refund`; payment events → `apply_gateway_payment`. The outcome is stored on the webhook row and returned.

### 3.4 Applying a payment (`apply_gateway_payment`, payments.py ~332)
Idempotent per `(provider, provider_payment_id)`: a DB partial unique index `uq_payment_provider_payment` (models.py ~236) and a `SELECT … FOR UPDATE` before inserting. Success: if already `confirmed` → `"already recorded"`; else create (or upgrade a previously recorded failure of the same payment id to) a `confirmed` `PaymentTransaction`, set the order `paid`, write `payment_confirmed`, call `issue_safely` (receipt/tax invoice PDF, emailed once via Celery) and `settle` (marks the application paid and drives completion/LMS access). Failure: recorded once; **a late failure never overwrites a recorded success**; the order becomes `failed` only if it was `active`.

### 3.5 Status refresh and reconciliation
- `refresh_order`: asks Cashfree `GET /orders/{id}/payments` and applies each payment through the same `apply_gateway_payment`; an unconfirmed `active` order past its expiry becomes `expired`.
- `refresh_for_student` (route `payments/refresh`, called by the "I have paid: check status" button **and automatically when the browser returns to `/internship-onboarding?order=…`**): covers the student's Cashfree orders in `active`, `created`, `failed`, and `expired` inside `RECONCILE_GRACE`.
- **Scheduled reconciliation** (`tasks._reconcile`, every 15 minutes UTC): `stale_orders()` selects Cashfree orders created more than 10 minutes ago and not checked in the last 10 minutes, `active`, or `failed`/`expired` while inside `RECONCILE_GRACE = 60 minutes` after expiry (limit 200 per run); each is re-read under `FOR UPDATE` and passed to `refresh_order`; then up to 100 `pending` refunds are polled with `refund_status`. Result is logged as `{'checked': n, 'confirmed': m}`. `paid`, `created` and `cancelled` orders are never asked about. `RECONCILE_GRACE` is a judgement (60 minutes), not a Cashfree figure.

### 3.6 Receipts, refunds, credit notes
- `financial.issue` creates a `FinancialDocument` (receipt, tax invoice if a GSTIN and tax mode are configured, or credit note for refunds) with a number `PREFIX-YYYY-NNNNNN` (credit notes `PREFIX-CN-YYYY-NNNNNN`, e.g. `RCPT-2026-000007`, `RCPT-CN-2026-000001`), a PDF in object storage, and an email through Celery (`send_document_task`) using the Email Studio template `internship_onboarding_receipt`.
- Refunds: `RefundService` (payments.py ~524): finance-only; one open refund per payment; Cashfree refund id derived from the refund row (`"RF" + id.hex[:30]`), so a retry is the same gateway request. `apply_gateway_refund` matches pending refunds by that id and the exact amount; on success `_confirm` marks it `confirmed`, adds a `waiver` transaction with note `refund_adjustment` for the part that is not an overpayment (so the ₹1 refund is counted once: the waiver lowers what is owed, the refund lowers what was paid), writes `refund_completed` and issues the credit note. Bank/UPI refunds are confirmed by finance with the transfer reference (`decide`).
- **Cashfree auto-refunds** (`report_auto_refund`, added in PR #163): `AUTO_REFUND_STATUS_WEBHOOK`-style notifications are acknowledged (200), matched to the payment by `cf_payment_id`, and reported on the student's timeline as `gateway_auto_refund` ("Cashfree refunded this payment itself; finance to check and record"). **The ledger is not changed automatically.** Before PR #163 these were refused with 400.

### 3.7 Data integrity summary
Unique index on `(provider, provider_payment_id)`; row locks on the application, order and payment; webhook event hash; exact amount/currency check; success never overwritten by failure; one open refund per payment; refund ids derived from rows. Known low-severity finding (handoff L-list, PR #163 branch `docs/CASHFREE_REVIEW_HANDOFF.md` section 2): a webhook racing a student status check can make the loser's request fail once on the unique index; no duplicate payment is possible.

## 4. What PR #163 changed in production code (10 files, +228/-9 including CI; no migration)

| File | Change |
|---|---|
| `modules/internship_onboarding/payments.py` | `RECONCILE_GRACE`, `RECONCILABLE_STATUSES`, `_inside_grace`; `stale_orders` and `refresh_for_student` cover failed and recently expired orders; `report_auto_refund`; webhook branch for `AUTO_REFUND*`. |
| `modules/internship_onboarding/tasks.py` | `_reconcile` uses `RECONCILABLE_STATUSES` for its re-check. |
| `modules/internship_onboarding/providers/cashfree.py`, `providers/base.py` | Parse `AUTO_REFUND*` bodies; `WebhookEvent.auto_refund_*`. |
| `modules/internship_onboarding/models.py` | Comment only (what `failed` means). |
| `apps/api/scripts/seed.py` | Standalone bootstrap seed imports two models that `Organization` foreign keys need (fixes `NoReferencedTableError`). |
| `apps/api/requirements.txt`, `apps/api/Dockerfile`, `apps/api/scripts/check_dependency_compat.py` | Celery stack pins + compatibility check (history document, section 2.5). |
| `.github/workflows/ci.yml` | Triggers for `master`, `PYTHONPATH` for migrations, compatibility step. |

Deliberately **not** changed: signature verification, webhook dedupe, amount/currency validation, the confirmation path, the ledger, the status model, the schema.

## 5. Sandbox test history (all on the owner's Mac staging stack unless marked Test; **the evidence directories are git-ignored and were never inspected by the Cloud session: every manual result below is OWNER-reported**)

Full table with qualifications: `docs/CASHFREE_SANDBOX.md` section 4a (PR #163 branch). Student names are synthetic labels, not people.

| Row | Scenario | Result | Evidence / identifiers |
|---|---|---|---|
| 1-3a | ₹2,000 order, hosted checkout, success webhook → confirmed once → receipt PDF + email; replayed webhook; replay audit | Passed (twice) | Owner-reported `./staging.sh evidence` (an example snapshot name is `20261103T072028Z`): 0 duplicate payments, 0 duplicate documents, 0 missing documents, 0 accounting entries; one email per receipt in Mailpit. Test: replay suites. |
| 4, 4a, 4b | ₹1 refund → refund webhook → credit note `RCPT-CN-2026-000001`; counted once; idempotency | Passed | Ledger: payment 2,000 + refund 1 + waiver 1; student owes 1,999, paid 1,999 net, balance 0. 0 refund-adjustment mismatches. |
| 5 | Failed payment (`testfailure@gocash`) | Passed | Stayed unpaid, no receipt, a successful retry created a new order. |
| 6 | Checkout closed / cancelled | Passed **on manual checks only** | Most likely closed before a method was chosen, which creates no Cashfree attempt; nothing in the evidence was reviewed. |
| 6a | A genuine `PAYMENT_USER_DROPPED_WEBHOOK` | **NOT OBSERVED** | Handler covered only by synthetic payloads. Cashfree documents the event; nothing found says the sandbox emits it. ERPX never marks Paid from a dropped event. |
| 7 / 7c | Lost webhook (gateway returned 503 while the payment succeeded) | Passed as **automatic recovery** | Receipts `RCPT-2026-000004` (first run) and `RCPT-2026-000005` (Student D, `ERPX-INT-2026-000007`). Most likely cause: the portal's automatic status check on the return page; **likely, not proven** (minute-resolution timeline; page-load and button call the same endpoint). |
| 7a | Late webhooks after the endpoint was restored | Passed | Two success notifications for payment `1471038895188844032`, both HTTP 200, nothing added. |
| 7b | **Student E**: manual "I have paid: check status" button, isolated with `./staging.sh gate on` | **Passed with qualifications** | `ERPX-INT-2026-000008`, payment `1471061513720561664`, receipt `RCPT-2026-000006` once. Gateway log: two `POST /payments/refresh` 200 at 08:29:00 and 08:33:55 UTC; the second aligns with the click, the first is **not attributed** to Student E. Evidence `20261103T083944Z` zeros. |
| 8 | **The Cashfree return-page blocker**: the first checkout stayed on Cashfree's return page; the second returned | **Unexplained, no code change** | Leading hypothesis (UNVERIFIED): the return URL is fixed at order creation (`FRONTEND_URL` + `/internship-onboarding?order=…`); on the Mac `FRONTEND_URL` is a quick-tunnel address, so a restarted tunnel or an order created before `./staging.sh up` picked up the new address leaves Cashfree redirecting to a dead address. In production `FRONTEND_URL` is fixed (`https://erp.pentrix.in`). Check by comparing the first order's `created_at` with when the tunnel address changed and the return URL in the Cashfree dashboard. |
| 9 | **Student F**: automatic scheduled reconciliation (`./staging.sh recon`, webhook 503, return page blocked, no student check, Beat and worker running) | **PASSED, one real run** | `ERPX-INT-2026-000009`, payment `1471080942373399040`, receipt `RCPT-2026-000007`. Mode on from 09:49:43Z; order created 09:50:22Z, payment 09:50:28Z, confirmed 10:15:00Z in the scheduled run (worker finished about 10:15:01Z, result `{'checked': 1, 'confirmed': 1}`); one payment, one receipt, one email, five integrity checks 0; automatic rollback reported. |
| 10 | **Student G**: success on the same order after a failed attempt, notification lost, scheduled task recovers | **PARTIALLY VERIFIED, accepted by the owner** | `ERPX-INT-2026-000010`, Cashfree order `ERPXIFBE8D1204F036125239A17FF`, mode on from 11:35:24Z. First attempt FAILED; Beat dispatched at 11:45 and 12:00 UTC; at 12:00 `{'checked': 1, 'confirmed': 0}` and the order was `failed` (it was **detected and recorded automatically**); three webhooks refused with 503; no student check. **Not observed:** the second, successful attempt on the same Cashfree order (the checkout redirected to the blocked return page and the visible UI offered no accessible retry path) and therefore the automatic recovery. Covered only by the 18 mocked regression cases (13 of the 18 fail against the old code). |

Other unobserved items: an `AUTO_REFUND` notification (mocked body only), API version `2026-01-01`, anything production, a Docker image build in the Cloud, real bash 3.2 in the Cloud.

### The Redis/Kombu failure (found during the row-10 preparation)
See the history document section 2.5, item 4: `VersionMismatch … redis-py versions 6.1.0 or later. You have 5.0.8`; worker and Beat in restart loops (`RestartCount=18`), API healthy; kombu 5.7.0 resolved because kombu was unpinned. **Recovered** by pinning, rebuilding the staging API image with `./staging.sh up` (data untouched) and a green `recon check`. OWNER-reported recovery; the pins and the checker are verified by tests and by GitHub's runner (compat step green in CI runs #7 and #8 on PR #163's branch against a real Redis service; runs #10 and #11 are on PR #164's branch, which does not contain that step).

### The staging stack
`ops/staging-cashfree/staging.sh` commands: `init`, `tunnel`, `up`, `seed`, `verify`, `sandbox-tests`, `gate on|off|status`, `recon check|run|status`, `evidence`, `network-check`, `refresh-app`, `recreate-network`, `status`, `logs`, `down`, `destroy`. The owner's Mac path is `~/erpx-cashfree-staging/ops/staging-cashfree` (OWNER; never `~/erpx-cf-staging`). The stack uses an **external** Docker network with a dedicated subnet (previously `10.253.247.0/24`), pinned community MinIO, Mailpit for mail, an nginx gateway whose rules can refuse the webhook, the return page or the status endpoint, and a quick-tunnel for Cashfree's webhook. It must not touch other projects' containers (the owner has unrelated "RASKGF" containers) or delete volumes.

## 6. Security considerations

- Secrets only in environment variables; never in the database or API responses; never logged (`__repr__`). Do not paste them anywhere, including this chat or the repository.
- Webhooks: HMAC verification of the raw body with timestamp window; hash-based dedupe; size cap; rate limit; unknown orders answered 200 without effect.
- The browser never decides an amount; success requires the exact amount/currency; the return page alone never confirms anything.
- Production guard: `CASHFREE_ENABLED` + `CASHFREE_ENV=production` + `CASHFREE_ALLOW_PRODUCTION` must all be set deliberately; the provider constructor refuses production otherwise.
- Rollback order matters (GIT, handoff section 5): with `CASHFREE_ENABLED=false` the webhook answers 503 and reconciliation stops, so rollback must stop new checkouts first and keep the plumbing on until in-flight payments settle.
- The Mac Compose stack binds only needed ports locally and runs on an external subnet; keep it sandbox-only.

## 7. Production restrictions (binding)

No production deployment of PR #163 has been authorized. No live Cashfree key, webhook or whitelist change has been made by the Cloud session. Production releases, merges and AWS changes are the owner's alone. The production MinIO image (`minio/minio:latest`) can no longer be pulled from the registry (MinIO stopped publishing community images, per the PR #163 handoff; UNVERIFIED on the host): preserve and pin the running image before any rebuild or recreate (PR #163 handoff section 4).

## 8. Unresolved cases and limitations

1. Real USER_DROPPED notification: not observed (row 6a).
2. Row 10 recovery on the same order: mocks only.
3. The stuck return page (row 8): unexplained.
4. `AUTO_REFUND` notification: mocked body only.
5. API version `2026-01-01`: untested (production stays on `2025-01-01`).
6. `RECONCILE_GRACE = 60 min`: a judgement.
7. Attribution of rows 7 and 7c: likely, not proven. One real run of the scheduled reconciliation (row 9).
8. Independent review of PR #163: none yet.

## 9. Release prerequisites (all OWNER actions; none executed)

1. Independent review and merge of #163 (after the CI decisions in the CI document).
2. Celery pins present in any production image build (never rebuild from the old `requirements.txt`).
3. A separate change passing `CASHFREE_*` variables through `docker-compose.prod.yml`, and the production secrets in `/opt/erpx/.env`.
4. Production keys; Cashfree webhook `https://erp.pentrix.in/api/v1/public/payments/cashfree/webhook`, version `2025-01-01`, events payment / failed / user-dropped / refund / auto-refund; domain whitelist; API IP whitelist if enabled.
5. Written authorization before `CASHFREE_ALLOW_PRODUCTION=true`.
6. Production MinIO image preserved and pinned (separate change).
7. A controlled-start decision: one internship, "Online (Cashfree)" enabled by finance, one low-value real payment by staff and its refund, then open to students, with a named rollback owner.
