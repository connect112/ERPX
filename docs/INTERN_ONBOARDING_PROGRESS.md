# Internship onboarding: progress

Requirements: the owner's master prompt "ERPX — Complete Automated Internship Onboarding, Acceptance & Payment Management
System" (all sections 0-33 apply). Design and gap matrix: `docs/internship-onboarding.md`.

| Item | Value |
|---|---|
| Branch | `claude/internship-onboarding` |
| Base | `master` at `958d346` (Bulk Download #160 merged; migration head `0097`) |
| Next migration numbers | `0098` (onboarding core), `0099` (payments); re-check `master` before merging |
| Draft PR | see the PR for this branch |

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

## Next (in order)

1. (done) Frontend: admin settings editor (modes, fees, deadlines, documents, form builder, accounts), dashboard, student
   detail, document review, payment verification; public student page `/internship-onboarding#t=...` with the steps
   and Cashfree hosted checkout (`sdk.cashfree.com/js/v3`).
2. **F** receipts/invoices (numbering, PDF, private storage, email, idempotent), refunds (ledger + Cashfree refund API),
   cancellations.
3. **G** reminders (7/3/1 days, configurable, deduplicated), bulk actions, automatic LMS grant on eligibility (reuse
   `OnboardingService.grant`), completion email.
4. **H** E2E in the browser, release and rollback scripts for the approved merge commit (`0098`/`0099` downgrade).

## Blockers and owner decisions

- **Cashfree documentation and sandbox are not reachable** from this cloud session (`www.cashfree.com` denied by the
  network policy). The adapter is built against the known API contract, with the API version configurable, and stays
  marked unverified until those hosts (and `sandbox.cashfree.com`) are allowed and a sandbox run is done.
- Malware scanning: no scanner in the stack (needs a ClamAV service); uploads are type-checked by content meanwhile.
- Whether internship fees post into `modules/accounting` (needs customer and account mapping); GST registration details
  for invoices; refund policy text; retention period for identity documents.

## Tests run

- `tests/unit/test_internship_onboarding_rules.py` 40 passed; `tests/api/test_internship_onboarding.py` 13 passed;
  `tests/api/test_internship_onboarding_payments.py` 13 passed (Cashfree with mocked HTTP and real HMAC signatures).
- Web: `tsc -b`, `eslint`, `vitest` (193 passed; 6 onboarding helper tests).
- Regression for touched shared code: offer letters, our internships, internship offers, email templates and Studio,
  RBAC: pass. Migrations `0098`/`0099`: upgrade, downgrade to `0097`, re-upgrade: pass; no drift against the models.

## How to continue

```bash
git fetch origin && git checkout claude/internship-onboarding && git pull
```
Then pick up the first unchecked item under "In progress / next". Local test setup: `docs/CLOUD_HANDOFF.md` section 11.
