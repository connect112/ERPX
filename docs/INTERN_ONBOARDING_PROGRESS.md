# Internship onboarding: progress

Requirements: the owner's master prompt "ERPX — Complete Automated Internship Onboarding, Acceptance & Payment Management
System" (all sections 0-33 apply). Design and gap matrix: `docs/internship-onboarding.md`.

| Item | Value |
|---|---|
| Branch | `claude/internship-onboarding` |
| Base | `master` at `958d346` (Bulk Download #160 merged; migration head `0097`) |
| Next migration numbers | `0098` (onboarding core), `0099` (payments); re-check `master` before merging |
| Draft PR | see the PR for this branch |

## Done

- Milestone A: repository audit, gap matrix, architecture (`docs/internship-onboarding.md`).
- `modules/internship_onboarding/config.py`: validated per-internship settings (modes, fees, deadlines, document
  requirements, custom form fields, declaration, bank/UPI accounts, communication); refuses contradictory settings.
- `modules/internship_onboarding/fees.py`: Decimal fee snapshot (discount, inclusive/exclusive tax, late fee).

## In progress / next (in order)

1. Unit tests for `config.py` and `fees.py`.
2. `state.py`: derived offer / document / payment / overall status (no stored overall status).
3. Models + migration `0098`: config + versions, templates + versions, applications (1:1 with
   `our_internship_selections`, reference, hashed token, drafts, acceptance + fee snapshot, deadline override,
   reopening), documents (versions, review), events, reference counters.
4. Services: config save (finance sections need `our_internships.finance.manage`), templates, invitation tokens
   (issue/rotate/revoke), reopening with late fee, student portal (open, draft, info corrections, form validation,
   document upload with content-type sniffing, accept/decline), document review → `selection.verification_status`.
5. Permissions: `our_internships.onboarding.review`, `our_internships.finance.view`, `our_internships.finance.manage`.
6. Offer email placeholders (`onboarding_link`, `onboarding_deadline`, `onboarding_start_date`, `internship_fee`,
   `late_fee`, `total_payable`, `application_reference`) on `internship_offer_letter`; link rotated when the email is sent.
7. Routes: admin (`/our-internships/{id}/onboarding-flow/...`, `/onboarding-templates`), public
   (`/public/internship-onboarding/{token}`), tests.
8. Milestone E: ledger + orders (`0099`), bank/UPI claims and finance verification, Cashfree adapter + webhook.
9. Frontend: admin config / dashboard / review / payment verification; student portal page.
10. Milestones F-H: receipts/invoices, refunds, reminders, bulk, completion + WhatsApp, automatic LMS, E2E, release scripts.

## Blockers and owner decisions

- **Cashfree documentation and sandbox are not reachable** from this cloud session (`www.cashfree.com` denied by the
  network policy). The adapter is built against the known API contract, with the API version configurable, and stays
  marked unverified until those hosts (and `sandbox.cashfree.com`) are allowed and a sandbox run is done.
- Malware scanning: no scanner in the stack (needs a ClamAV service); uploads are type-checked by content meanwhile.
- Whether internship fees post into `modules/accounting` (needs customer and account mapping); GST registration details
  for invoices; refund policy text; retention period for identity documents.

## Tests run

- None yet for this branch (config and fees only smoke-imported).

## How to continue

```bash
git fetch origin && git checkout claude/internship-onboarding && git pull
```
Then pick up the first unchecked item under "In progress / next". Local test setup: `docs/CLOUD_HANDOFF.md` section 11.
