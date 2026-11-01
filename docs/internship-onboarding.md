# Internship onboarding, acceptance and payments: audit and architecture

Branch `claude/internship-onboarding`, based on `master` at `958d346` (Bulk Download, #160). Migration head on `master`: `0097`.

## 1. What exists today (repository evidence)

| Area | Where | What it does |
|---|---|---|
| Internship + selection | `modules/our_internships/models.py` | `OurInternship`; `InternshipSelection` (one per student on the shortlist) already carries offer status (`not_sent/queued/sent/failed`), the student's response (`awaiting/accepted/declined`, recorded by staff), document verification (`pending/verified/rejected` + note), a **manually confirmed** payment (`pending/paid`, amount, reference, received date, confirming user) and LMS access (`not_granted/granted/revoked`). |
| Manual onboarding + LMS | `modules/our_internships/onboarding.py` | Staff set the statuses per student or in bulk; `grant_blockers` refuses LMS access until verified **and** paid; `grant` creates or reuses the student account and enrolment idempotently and refuses someone else's account. |
| Offer letters | `letters.py`, `letter_tasks.py`, `letter_models.py` | Versioned PDF letters per student, approval, release, Celery email with retries and delivery history. The email is an Email Studio template (`internship_offer_letter`) or the letter settings' text. |
| Email | `packages/email/registry.py`, `modules/email_studio` | Template registry with declared variables; studio templates may only use declared variables. |
| Instructor access | `access.py` | `internship_access` / `exam_access`, time-boxed instructors, no deletes. |
| Files | `modules/internship_learning/files.py`, `packages/storage` | MinIO, private objects, short-lived presigned links, blocked executable extensions, 25 MB cap. |
| Audit | `modules/audit/hooks.py` | Every ORM create/update/delete is audited with user, IP, request id; binary columns are fingerprinted; models can exclude fields. |
| Public token pattern | `modules/workshop_exams/routes.py` (`public_router`) | Unauthenticated routes keyed by an unguessable token, rate-limited; public page in `apps/web`. |
| Secrets at rest | `modules/social_media/token_crypto.py` | Fernet encryption pattern. |
| Accounting | `modules/accounting/invoices`, `receipts`, `payments` | Double-entry invoices need a customer and chart-of-accounts accounts. |
| Pentrix payments | `modules/pentrix_ops` | Mirror of Razorpay/Stripe payments made in Pentrix; not a gateway integration. |

Not present anywhere: student-facing onboarding, onboarding links, per-internship onboarding configuration, fees, deadlines, custom forms, document uploads by students, a payment ledger, any gateway integration, invoices for internship fees, refunds, malware scanning.

## 2. Gap matrix (prioritised)

| # | Feature | Current | Missing | Reuse | Change | Risk | Priority |
|---|---|---|---|---|---|---|---|
| 1 | Per-internship configuration (modes, fees, deadlines, documents, form, declaration, methods) | none | everything | pydantic config pattern of `letter_config.py` | new config + versions | contradictory settings | P0 |
| 2 | Application reference + one onboarding record per student | `offer_reference` on the letter only | stable application record | `InternshipSelection` (1:1) | new table keyed to the selection | duplicate records | P0 |
| 3 | Secure links | none | hashed tokens, expiry, revoke, rotate, rate limits | public router pattern, limiter | new | token leakage | P0 |
| 4 | Offer-email placeholders | offer email variables | onboarding link/deadline/fees/reference | `internship_offer_letter` definition, `_send_letter` | add variables, rotate link on send | link in mail must match stored hash | P0 |
| 5 | Student portal: info, custom form, drafts | none | all | public page pattern | new API + page | data overwrite | P0 |
| 6 | Document submission + review | one manual verification status | per-document versions, review, resubmission | storage, files helper | new table; aggregate drives `verification_status` | sensitive IDs | P0 |
| 7 | Offer acceptance/decline | staff-recorded response | student consent record, fee snapshot | `offer_response` stays the single source | acceptance record on the application | legal record integrity | P0 |
| 8 | Deadlines, individual reopening, late fee | none | server-side enforcement, per-student override | | fields + events | boundary/time zone | P0 |
| 9 | Payment ledger, bank/UPI proofs and verification | `payment_status` pending/paid by hand | ledger, proofs, UTR uniqueness, finance permission | `payment_status=paid` stays the LMS gate | new tables; confirmed ledger total sets `paid` | double charge, fraud | P0 |
| 10 | Cashfree | none | adapter, orders, webhook signature, reconciliation, refunds | provider-adapter, Celery | new | money; unverified API docs (network) | P1 |
| 11 | Invoices/receipts | accounting invoices (needs accounts) | onboarding receipts with own numbering, PDF, email | PDF infra, storage, email | new; posting to accounting is an owner decision | tax correctness | P1 |
| 12 | Refunds/cancellations | none | ledger entries, approval, provider refund | ledger | new | money | P1 |
| 13 | Reminders, bulk actions, completion page, WhatsApp, auto LMS | bulk status update, LMS grant | scheduled reminders, eligibility automation | Celery beat, `OnboardingService.grant` | new tasks | spam, duplicate grants | P2 |
| 14 | Templates (reusable onboarding setups) | none | versioned templates applied to internships | config schema | new | silent changes to accepted terms | P1 |
| 15 | Installments | none | schedule + balance | ledger | later | partial = paid mistakes | P3 (off by default) |
| 16 | Malware scanning | none anywhere | scanner service | | optional clamd client built, off by default (`CLAMAV_ENABLED`); needs a ClamAV service (owner) | infected uploads | P2 (owner decision) |

## 3. Architecture

**One record per student.** `InternshipSelection` remains the student's place on the internship and keeps the fields the
manual process and LMS grant already use. A new `internship_onboarding_applications` row (1:1 with the selection) holds
what the automated flow adds: the application reference, the hashed link, drafts, the acceptance record with its fee
snapshot, individual deadlines. Nothing is duplicated:

- `selection.offer_response` stays the authoritative accept/decline; the student's action sets it, and staff can still set it by hand.
- `selection.verification_status` stays the gate for LMS; it becomes `verified` when every required document is verified
  (or stays manual when document checks are off).
- `selection.payment_status = paid` stays the gate for LMS; it is set when the confirmed ledger total reaches the
  amount payable (or by hand, as today).
- The overall status is **derived** (`state.py`), never stored, from these fields plus documents and the ledger.

**Configuration** is a validated pydantic document (`config.py`) stored per internship with a version number; every
saved change creates an immutable version row. An application records the config version and the fee snapshot the
student accepted, so later edits never change accepted terms. **Templates** are the same document, versioned, applied by
copying into an internship's configuration.

**Links.** 32-byte random tokens; only the SHA-256 is stored. A token is rotated when an invitation is (re)sent, so the
newest email carries the working link and older links stop working. Expiry = the student's effective deadline (or the
reopened expiry). Public routes are rate-limited, never log the token, and resolve the application before anything else.

**Payments.** One ledger (`internship_payment_transactions`) for every method. Orders (`internship_payment_orders`) hold
the amount fixed when the obligation is created. Manual bank/UPI claims are `awaiting_verification` until a finance user
confirms receipt; a UTR/reference is unique per organization among non-rejected claims. Cashfree is an adapter behind a
`PaymentProvider` interface (create order, fetch status, verify webhook, refund): confirmation comes only from a verified
webhook or a server-side status fetch whose order id, amount and currency match; browser redirects are never trusted.
Webhooks are stored by hash for idempotency and processed safely when duplicated or out of order.

**Permissions.** `our_internships.view/manage` as today; new `our_internships.onboarding.review` (documents) and
`our_internships.finance.view/manage` (payments, payment accounts, fees, refunds). The Administrator role receives them
through the existing seed rule; narrower roles can be built in Roles.

## 4. Security and privacy

Hashed tokens; no token in logs (routes take it in the path but log only the application id); rate limits; tenant
checks on every query; documents private in MinIO under `onboarding/<org>/<application>/`, real type checked by content
(PDF/JPEG/PNG signatures), size limits, executable types blocked; presigned links of a few minutes for reviewers only;
Aadhaar is **not** a default requirement (configurable, with an "alternative ID accepted" note); audit via the existing
hooks with document bytes never stored in rows; payment-account details editable only with finance permission; gateway
secrets only from the environment (`CASHFREE_*`), never in the database, API responses or logs.

Decided by the owner: INR 2,000 default fee; GIR Technologies as the default issuer (no GSTIN or tax details assumed,
so receipts, not tax invoices); document approval by authorized administrators; payment timing and LMS access per
internship; Cashfree off until merchant configuration and sandbox acceptance.

Still open (configurable, nothing assumed): refund policy wording (`policies.refund_policy`), identity-document
retention (`policies.identity_document_retention_days`, display only), GST details, running a ClamAV service, posting
fees into the accounting ledger. Manual shortcuts that set "paid"/"verified" need the finance/reviewer permission once
an internship uses self-service onboarding. Readiness matrix: `docs/INTERN_ONBOARDING_PROGRESS.md`.

## 5. Phases and status

| Milestone | Scope | Status on this branch |
|---|---|---|
| A | Audit, gap matrix, architecture | done |
| B | Config + versions, templates, references, links, deadlines/extensions | done |
| C | Student API and page: open, info, form drafts, documents, accept/decline | done |
| D | Review queue, reopen, dashboard, events, permissions | done |
| E | Ledger, bank/UPI, Cashfree adapter, late fees | done; Cashfree not yet sandbox-verified (blocked host) |
| F | Receipts/invoices/credit notes, refunds, cancellation | done |
| G | Reminders, CSV/bulk exports, completion email, WhatsApp, automatic LMS, templates UI | done (installments: deferred, not built) |
| Hardening | Owner defaults, refund/claim race guards, manual-shortcut permissions, policies, optional ClamAV | done; see readiness matrix |
| H | Release and rollback scripts, browser E2E | done locally; sandbox E2E pending |

Each PR states what was verified and what was not.
