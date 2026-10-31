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

## Remaining

1. **Cashfree sandbox acceptance** (blocked): allow `www.cashfree.com` and `sandbox.cashfree.com` under Network access,
   provide sandbox keys as environment secrets (never in chat or the repo), then: verify the adapter against the current
   docs (API version, order/payment/refund fields, webhook signature), run order -> pay -> webhook -> receipt -> refund in
   the sandbox, and record the results here.
2. Owner decisions below; installments (designed in the ledger, switched off; not built as a schedule UI).
3. Release: owner approves the exact merge commit, then `ops/release-internship-onboarding/` 01 -> 02a (C1) -> 02b (C2)
   -> 03 (C3), outside 01:45-04:30 UTC. Acceptance as a plain Administrator: configure one internship in hybrid mode with
   bank/UPI only (Cashfree off), send one test student their link, complete the flow, confirm the payment, check the
   receipt PDF opens and the email arrives, check the Storage Manager still lists `backups/` as protected.

## Blockers and owner decisions

- **Cashfree documentation and sandbox are not reachable** from this cloud session (`www.cashfree.com` denied by the
  network policy). The adapter is built against the known API contract, with the API version configurable, and stays
  marked unverified until those hosts (and `sandbox.cashfree.com`) are allowed and a sandbox run is done.
- Malware scanning: no scanner in the stack (needs a ClamAV service); uploads are type-checked by content meanwhile.
- Whether internship fees post into `modules/accounting` (needs customer and account mapping); GST registration details
  for invoices; refund policy text; retention period for identity documents.

## Tests run (latest)

- Backend: onboarding rule tests 40, API tests 13 (core) + 15 (payments, completion, reminders) + 8 (finance, bulk
  download source) = 76 passed; regression (bulk exports, offer letters, our internships, internship offers, email
  templates and Studio, RBAC, bulk filenames) 169 passed.
- Migrations `0098`-`0100`: upgrade, downgrade to `0097`, re-upgrade; no drift against the models; rollback with data
  keeps Storage Manager and Bulk Download rows byte-identical.
- Web: `tsc -b`, `eslint`, `vitest` 193 passed.
- Browser (plain Administrator + student on a 390 px screen, synthetic data): configure, link, save/resume, uploads,
  accept, bank claim, finance confirmation, verification, completion with WhatsApp link, receipt download, partial refund
  with credit note; no console errors. Found and fixed: deadlines in the browser's zone, zeros while loading, refunded
  amount asked again.
- Not run: anything against the real Cashfree sandbox (blocked network).

## How to continue

```bash
git fetch origin && git checkout claude/internship-onboarding && git pull
```
Then pick up the first item under "Remaining". Local test setup: `docs/CLOUD_HANDOFF.md` section 11.
