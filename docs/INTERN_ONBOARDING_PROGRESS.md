# Internship onboarding: progress

Requirements: the owner's master prompt "ERPX — Complete Automated Internship Onboarding, Acceptance & Payment Management
System" (all sections 0-33 apply). Design and gap matrix: `docs/internship-onboarding.md`.

| Item | Value |
|---|---|
| Branch | `claude/internship-onboarding` |
| Base | `master` at `958d346` (Bulk Download #160 merged; migration head `0097`) |
| Migrations on this branch | `0098` (onboarding core), `0099` (payments), `0100` (receipts, refunds); re-check `master` before merging |
| Draft PR | https://github.com/connect112/ERPX/pull/161 |

## Done (backend, database-backed, tested)

- **A** audit, gap matrix, architecture (`docs/internship-onboarding.md`).
- **B** validated, versioned per-internship settings (finance sections need `our_internships.finance.manage`; account
  numbers masked otherwise); versioned templates (create, update, duplicate, archive, apply; accepted terms untouched);
  application references `ERPX-INT-<year>-<n>`; personal links (SHA-256 only, rotated per send, revocable, URL fragment
  + `X-Onboarding-Token` header so they never reach logs); deadlines enforced server-side; individual reopening with at
  most one late fee, waivable. Migrations `0098` (onboarding) and `0099` (payments).
- **C** student API: view, drafts with form validation, proposed corrections (applied only after staff review),
  document uploads type-checked by content and versioned, acceptance (declaration, terms version, fee snapshot) and
  decline writing the selection's existing `offer_response`; read-only after expiry.
- **D** document review (`our_internships.onboarding.review`, 3-minute previews, restricted sensitive names, reasons
  required) driving the selection's `verification_status`; dashboard with derived statuses and money totals; student
  detail with timeline; offer emails carry the onboarding placeholders with a fresh link; invitation email task.
- **E** one ledger for every method; bank/UPI claims (UTR unique per organization among live claims, proof required)
  confirmed only by `our_internships.finance.manage`; amount differences must be explained and leave a balance (never
  "paid" on part of the fee); staff-recorded payments; payment-order modes; zero-fee internships; Cashfree adapter
  (orders, payment status, HMAC webhook with age limit, duplicate/out-of-order handling, amount/currency matching,
  reconciliation task every 15 min) behind a provider interface; production refused unless explicitly authorised.
  Confirmed payment sets the selection's existing `payment_status = paid` (the LMS gate).

- **Frontend** staff panel in Our Internships > Onboarding (students board, payment checks, settings editor with form and
  document builders, templates, student detail) and the public student page `/internship-onboarding#t=...`.
  Browser-checked as a plain Administrator plus a student on a 390 px screen: configure, link, save and resume, two
  uploads, accept, bank claim, finance confirmation, document verification, completion page with WhatsApp link;
  token removed from the address bar; no console errors. Duplicate UTR correctly refused (409).

- **G (core)** completion recorded once when every requirement is met (acceptance, document review or payment
  triggers it), then automatic LMS access through the existing idempotent `OnboardingService.grant` when the internship
  uses automatic access (a zero-fee internship settles the existing payment gate as "No fee"); a sweep (`:07`/`:37`)
  catches up missed completions, retries LMS grants (a waiting reason is noted once, not every run) and sends deadline
  reminders once per student and configured day (not to declined, cancelled, completed or link-less students).

- **F** receipts (or a Tax Invoice only with an issuer GSTIN and a tax treatment; tax split from the accepted fee),
  credit notes; one per confirmed transaction, numbered per organization/series/year, immutable PDF in private storage,
  emailed with retries (never touching the payment), student and staff download, staff resend. Refunds: finance only,
  never above what is left of the payment; bank/UPI refunds confirmed with the transfer reference; Cashfree refunds
  through the adapter (refund API + refund notification + status check); a confirmed refund lowers what is owed
  (except returned overpayment). Cancellation/withdrawal by staff. Migration `0100`.
- **G (rest)** completion email once; status and payments CSV exports (formula-safe, money only for finance); Bulk
  Download source for onboarding documents (reviewers); Templates tab (preview, rename, duplicate, archive).
- **H** release scripts `ops/release-internship-onboarding/` (from the proven bulk-download set: 0097 -> 0100,
  rollback to 0097 only, backup-window guard, own rollback-target file). Rollback verified locally with data: Storage
  Manager and Bulk Download rows byte-identical, onboarding tables gone, re-upgrade works.

## Final hardening (release readiness)

Owner decisions applied (no legal or tax details invented):

| Decision | How it is applied | Evidence |
|---|---|---|
| INR 2,000 default fee | `Fees.base_amount` defaults to 2000 (INR); each internship can change it (finance permission). Payment itself stays off until staff enter the organization's bank/UPI details and switch it on. | unit `test_the_default_fee_is_inr_2000...`; browser: settings show 2,000.00, student sees ₹2,000.00 |
| Authorized administrators approve documents | Review needs `our_internships.onboarding.review`; now also the manual "verified" shortcut on self-service internships | API `test_document_review_drives...`, `test_manual_shortcuts_need_finance_or_reviewer...` |
| GIR Technologies is the default issuer | `Issuer.legal_name` defaults to "GIR Technologies"; address, GSTIN and tax stay empty, so documents are payment receipts, never tax invoices | unit `test_gir_technologies_issues_plain_receipts...`; browser |
| Payment timing and LMS access per internship | `modes.payment_order` (after submission / after document approval) and `modes.lms_access` (manual / automatic) | unit `test_payment_timing_and_lms_access...`, `test_payment_order_modes` |
| Cashfree disabled without merchant configuration | `CASHFREE_ENABLED=false` by default, empty keys refused, production also needs `CASHFREE_ALLOW_PRODUCTION`; new: Cashfree cannot be added as a method while not enabled, is hidden from students, and is shown as "not set up" in Settings | API `test_cashfree_cannot_be_offered...`; browser |

Audit results (payment and refund state machines):

- **Duplicate transactions**: a bank/UPI reference is unique per organization among live claims (partial unique index);
  a gateway payment is unique per provider payment id; new: a student's claims are serialized on their application
  row, so two tabs or a double submit cannot create two claims; one checkout order per obligation (same lock).
- **Webhook replay**: signature (HMAC-SHA256 of timestamp + raw body) and timestamp age checked; each notification
  stored by hash and processed once; out-of-order notifications cannot move a payment backwards; money is confirmed
  only by a verified notification or a server-side status fetch whose order, amount and currency match.
- **Refund idempotency** (gap fixed): the payment row is locked and a new refund is refused while another refund of the
  same payment is pending or awaiting confirmation (409); never more than what is left of the payment; the gateway
  refund id is derived from the refund row, so a retried provider call carries the same id.
- **Unauthorized financial changes** (gap fixed): fees, payment accounts and issuer need `finance.manage`, as do claim
  verification, recorded payments, refunds and late-fee waivers. The existing manual shortcuts (`our_internships.manage`,
  including time-boxed instructors) could mark a self-service student "paid" or "verified" without the ledger; on
  automated/hybrid internships they now need `finance.manage` / `onboarding.review`. Staff-only internships are unchanged.
- **Outstanding balances**: Decimal with half-up rounding; a confirmed refund lowers what is owed (except returned
  overpayment), so the student is not asked to pay it again; "paid" is set only when confirmed money covers the
  payable amount and is never removed automatically (a full refund is followed up by staff, by design).

Audit results (links, documents, tenancy, forms, deadlines, overrides): tokens stored only as SHA-256, carried in the
URL fragment and a header (never in server logs), rotated on every send, revocable, revoked on cancellation; links
expire with the student's effective deadline and are read-only afterwards; reopening is per student with at most one
late fee. Uploads are checked by content (PDF/JPEG/PNG signatures) and size, stored privately under
`onboarding/<org>/<application>/`, previewed through 3-minute links by reviewers only; sensitive document names are
hidden from non-reviewers and never emailed. Every staff query is scoped by organization and internship (cross-tenant
test); public routes resolve everything from the token. Form answers are validated server-side, unknown keys dropped,
nothing is executed. No new findings beyond the two gaps above.

New, off by default or empty until configured:

- **Virus scanning (ClamAV)**: `CLAMAV_ENABLED=false`, `CLAMAV_HOST`, `CLAMAV_PORT`, `CLAMAV_TIMEOUT_SECONDS`
  (`modules/internship_onboarding/scan.py`, clamd `INSTREAM`). Off: uploads are recorded as `not_scanned` and staff see
  "not virus-scanned". On: every document and payment proof is scanned before storage; infected files are refused;
  if the scanner is unreachable or errors, uploads are refused (fail closed). Needs a clamd service, which is not in
  the stack; nothing claims a file was scanned unless clamd said so.
- **Refund policy wording** (`policies.refund_policy`): shown to the student before acceptance and stored word for word
  with their acceptance. Empty by default.
- **Identity-document retention** (`policies.identity_document_retention_days`): shown to students and on each
  sensitive document as the date its period ends. Not set by default; files are not deleted automatically.
- Columns `internship_onboarding_documents.scan_status` and `internship_payment_transactions.proof_scan_status` added
  to the unmerged migration `0100` (no new migration; release scripts unchanged).

## Release preparation (final corrections)

- **Identity documents need virus scanning**: a document marked sensitive cannot be saved in the settings, and cannot
  be uploaded, while `CLAMAV_ENABLED` is off (settings saved earlier stop accepting uploads too; the student is told the
  team will collect it another way). A requirement named Aadhaar must be marked sensitive. Nothing unscanned is stored.
- **No consent without the refund policy**: settings where students pay through their link are refused until the
  refund policy wording is entered; it is shown above the agreement and stored with the acceptance.
- **No silent indefinite retention**: requesting identity documents requires a retention period; the board counts files
  past it; a reviewer removes each file (storage object deleted, record kept with who and when, excluded from previews
  and Bulk Download). Automatic deletion stays off. Columns `removed_at`, `removed_by_user_id` added to unmerged `0100`.
- Release checkpoint C1 also prints `virus scanning enabled` (expect False) and the three document safety columns.
- Deployment checklist: `ops/release-internship-onboarding/CHECKLIST.md`.

## Production readiness matrix

| Capability | Status | Notes |
|---|---|---|
| Manual (staff-only) onboarding, unchanged behaviour | Verified | regression suites; default mode for every internship |
| Hybrid/automated self-service: links, form, drafts, uploads, accept/decline, deadlines, reopen | Verified | API tests + browser (plain Administrator, 390 px student) |
| Document review by authorized administrators | Verified | reviewer permission; manual shortcut guarded |
| Bank transfer / UPI with finance verification | Requires configuration | organization's bank account / UPI ID per internship (finance permission) |
| Default INR 2,000 fee | Verified | changeable per internship |
| Payment receipts issued by GIR Technologies | Requires configuration | address and footer optional; legal name can be changed |
| GST tax invoices | Requires configuration | only after a GSTIN, tax treatment and rate are entered by finance; no tax details assumed |
| Refunds (bank/UPI) with credit notes | Verified | one open refund per payment; finance only |
| Refund policy wording | Requires configuration (enforced) | settings where students pay through their link are refused without it; shown before acceptance and stored with it |
| Identity documents (Aadhaar, other government ID) | Blocked until ClamAV | refused (settings and upload) while `CLAMAV_ENABLED` is off; Aadhaar must be marked sensitive |
| Identity-document retention | Requires configuration (enforced) | required whenever identity documents are requested; overdue files counted on the board; a reviewer removes each file (record kept); automatic deletion **deferred** |
| Reminders, completion email, automatic LMS access, CSV exports, Bulk Download source | Verified | beat entries `:07`/`:37` and every 15 min need the worker and beat deployed |
| Virus scanning (ClamAV) | Requires configuration | code ready, off; release prerequisite for identity documents only; needs a clamd service before `CLAMAV_ENABLED=true` |
| Cashfree online payments and refunds | Blocked | sandbox acceptance not done (network policy, credentials); keep `CASHFREE_ENABLED=false` |
| Installment plans | Deferred | not built; students pay the full amount due (shown in Settings) |
| Posting fees into `modules/accounting` | Deferred | needs customer and account mapping (owner decision) |
| Release scripts and rollback (0097 -> 0100 -> 0097) | Verified locally | production run is the owner's: `ops/release-internship-onboarding/CHECKLIST.md` |
| Real MinIO (uploads, previews, receipts, Bulk Download ZIP) | Requires acceptance | tested on an S3 stand-in only; step 4 of the checklist |

## Cashfree sandbox validation (to do later, with authorization)

Nothing below has been run; the mocked tests (`tests/api/test_internship_onboarding_payments.py`) are not a substitute.

1. Network access for the session/environment: `www.cashfree.com` (documentation), `sandbox.cashfree.com` (sandbox
   API). Later, production only with owner approval: `api.cashfree.com`. Students' browsers load
   `https://sdk.cashfree.com/js/v3/cashfree.js`; if the production proxy sets a Content-Security-Policy, allow it there.
2. Official documentation to re-check against the adapter (`providers/cashfree.py`), under `https://www.cashfree.com/docs/`:
   Payment Gateway API reference for Create Order (`POST /pg/orders`), Get Payments for an Order
   (`GET /pg/orders/{order_id}/payments`), Create Refund (`POST /pg/orders/{order_id}/refunds`), Get Refund
   (`GET /pg/orders/{order_id}/refunds/{refund_id}`); the current `x-api-version` (adapter default `2023-08-01`,
   configurable through `CASHFREE_API_VERSION`); webhook payloads and signature verification (`x-webhook-signature`,
   `x-webhook-timestamp`); payment and refund webhook event types; sandbox test cards/UPI IDs.
3. Credentials: sandbox App ID and Secret Key from the Cashfree merchant dashboard (test mode), set only as environment
   secrets `CASHFREE_APP_ID` / `CASHFREE_SECRET_KEY` with `CASHFREE_ENABLED=true`, `CASHFREE_ENV=sandbox`; never in
   chat, the repository or the database.
4. Webhook: register `https://<api host>/api/v1/public/payments/cashfree/webhook` for payment success/failure and
   refund status in the dashboard. It must be a public HTTPS URL, so the webhook leg needs a staging server; a cloud
   session can only verify the status-fetch path (`refresh`, reconciliation task).
5. Acceptance run (sandbox money only): order -> pay with a test instrument -> webhook (and replay of the same webhook)
   -> receipt -> partial refund -> refund webhook -> credit note; failed payment; amount/currency mismatch refused;
   record the results here. Production stays off until the owner authorizes `CASHFREE_ALLOW_PRODUCTION`.

## Remaining

1. Cashfree sandbox acceptance (blocked; checklist above).
2. Owner: refund policy text, GST details if tax invoices are wanted, retention period, whether to run a ClamAV service,
   accounting posting.
3. Release: owner approves the exact merge commit, then `ops/release-internship-onboarding/` 01 -> 02a (C1) -> 02b (C2)
   -> 03 (C3), outside 01:45-04:30 UTC. Acceptance as a plain Administrator: configure one internship in hybrid mode with
   bank/UPI only (Cashfree off), send one test student their link, complete the flow, confirm the payment, check the
   receipt PDF opens and the email arrives, check the Storage Manager still lists `backups/` as protected.

## Tests run (latest)

- Backend: onboarding rule tests 40 + hardening unit tests 11 + API tests 13 (core) + 15 (payments, completion,
  reminders) + 8 (finance) + 6 (hardening: Cashfree not offerable, refund policy and retention with reviewer removal,
  identity-document and consent safeguards, scanning of documents and payment proofs, manual-shortcut permissions)
  = 93 passed; regression (bulk exports, offer letters, our internships, internship offers, email templates and Studio,
  RBAC, bulk filenames) 192 passed.
- Migrations `0098`-`0100`: downgrade to `0097` and re-upgrade after the column additions; no drift between the
  onboarding models and the migrated schema; earlier rollback with data kept Storage Manager and Bulk Download rows
  byte-identical.
- Web: `tsc -b` clean, `eslint` 0 errors, `vitest` 193 passed.
- Browser (plain `Administrator` role, not Super Admin, + student on a 390 px screen, synthetic data, scanning off):
  identity documents refused in settings (422) and not uploadable by the student while ordinary documents upload;
  board shows a file past retention; reviewer removed it (object gone from the S3 stand-in, record kept); settings
  explain the scanning requirement; refund policy above the agreement; INR 2,000; no console errors. Earlier rounds:
  full flow through payment, receipt and partial refund; defaults, Cashfree "not set up", installments unavailable.
- Not run: the real Cashfree sandbox (blocked network, no credentials); a real clamd (a local fake answered the
  protocol); real MinIO (acceptance step 4 of the checklist).

## How to continue

```bash
git fetch origin && git checkout claude/internship-onboarding && git pull
```
Then pick up the first item under "Remaining". Local test setup: `docs/CLOUD_HANDOFF.md` section 11.
