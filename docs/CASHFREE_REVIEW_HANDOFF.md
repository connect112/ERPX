# PR #163 — final review handoff (Cashfree sandbox acceptance, reconciliation fix, Celery dependency pin)

Status: manual Cashfree **Sandbox** testing is closed. Nothing here has been deployed, merged or enabled; Cashfree stays off in production.
This document is for the independent reviewer and for the owner. It separates what changed, what to check, what is a release blocker, and
what is an accepted limitation. Facts come from the repository, from the cloud session's test runs, and from the owner's reports of the
Mac sandbox runs (the Mac evidence directories are git-ignored and **were not inspected by the author**). The author also wrote the code
under review, so this is a self-review plus automated tests, **not** an independent review; that is what this handoff asks for.

Companion record: `docs/CASHFREE_SANDBOX.md` (acceptance results, rows 1-10, sections 4a-i to 4a-v).

---

## 1. The exact code changes that need independent review

Branch `claude/cashfree-sandbox-readiness`, 22 commits on `master` at `86e4a86` (master has not moved). **No database migration** is
included. The production-facing change is 10 files, +223/-7 lines. Everything else in the PR (27 files, about 4,400 lines under
`ops/staging-cashfree/`, `tests/`, `docs/`) is staging tooling, tests and documentation and does not run in production.

See it with:
```
git diff origin/master...origin/claude/cashfree-sandbox-readiness -- modules apps .github
```

| File | Change | Why | What to check |
|---|---|---|---|
| `modules/internship_onboarding/payments.py` | `RECONCILE_GRACE` (60 min), `RECONCILABLE_STATUSES = ("active","failed","expired")`, `_inside_grace()`; `stale_orders()` now also selects `failed`/`expired` orders inside the grace window; `refresh_for_student()` also covers `expired` inside the window; `handle_webhook()` routes `AUTO_REFUND*` events to new `report_auto_refund()` | A FAILED/USER_DROPPED attempt marks the local order `failed`, which scheduled reconciliation ignored, so a later success on the same Cashfree order with a lost notification stayed unrecorded until the student pressed the button. Auto-refund notifications carry no order block and were refused (400) | The SQL conditions; that `paid`/`created`/`cancelled` are never selected; that the spacing (10 min after creation and between checks) and the 200-per-run limit are unchanged; that `report_auto_refund()` writes only a timeline event and never touches the ledger |
| `modules/internship_onboarding/tasks.py` | `_reconcile()` accepts `RECONCILABLE_STATUSES` instead of only `active` (lazy import inside the function) | Same | That a `paid` order is skipped under the row lock |
| `modules/internship_onboarding/providers/cashfree.py`, `providers/base.py` | `parse_webhook()` reads `AUTO_REFUND*` bodies; `WebhookEvent` gains `auto_refund_payment_id`, `auto_refund_amount` | Same | That the normal payment/refund parsing path is byte-for-byte as before for every other event type |
| `modules/internship_onboarding/models.py` | comment only (what `failed` means) | Documents the status model | nothing executable |
| `apps/api/scripts/seed.py` | two model imports (`Account`, `SalaryComponent`) | The standalone bootstrap seed failed with `NoReferencedTableError` on a fresh database | imports only; covered by `tests/integration/test_bootstrap_seed.py` |
| `apps/api/requirements.txt` | pins the Celery messaging stack: `kombu==5.6.2`, `amqp==5.4.1`, `billiard==4.3.1`, `vine==5.1.0` (celery 5.4.0 and redis 5.0.8 unchanged) | section 3 | that the set is compatible; that no unrelated pin moved |
| `apps/api/Dockerfile` | builder stage runs `scripts/check_dependency_compat.py` after `pip install` | the build fails instead of the containers | that it adds no network access and runs in the builder stage only |
| `apps/api/scripts/check_dependency_compat.py` (new) | checks declared requirements of celery/kombu/amqp/billiard/vine (including the `redis` extras) against what is installed; `--broker URL` also opens a real Kombu connection | section 3 | the logic; exit codes |
| `.github/workflows/ci.yml` | one step running the check against CI's Redis service | section 3 | **CI does not currently trigger on this branch's base** (section 6, B2) |

**Deliberately not changed:** signature verification, the webhook dedupe, amount/currency validation, the confirmation path
(`apply_gateway_payment`), the refund service, the ledger and its constraints, the provider-status mapping, the fee/amount calculation
(`start_checkout`), the production guards, and the database schema.

Tests that exercise these changes (all pass in the cloud session on real PostgreSQL, mocked Cashfree HTTP, real signatures):
`tests/api/test_internship_onboarding_cashfree_attempts.py` (18, **13 fail against the original code**),
`test_internship_onboarding_reconcile_task.py` (4, includes the real `_reconcile()` body, the Beat entry and the report SQL),
`test_internship_onboarding_cashfree.py` (7), `tests/unit/test_dependency_compat.py` (12). All 407 tests in `tests/unit` and all 76 in
`tests/api/test_internship_onboarding*.py` pass. Run them yourself: `pytest tests/unit tests/api/test_internship_onboarding*.py`.

---

## 2. Security considerations: payments, refunds, webhooks, reconciliation

Controls that exist (verified by reading the code; the tests cover each):

| Concern | Control | Where |
|---|---|---|
| Forged webhooks | HMAC-SHA256 over `timestamp + raw body` with the merchant secret, compared with `hmac.compare_digest`; bad signature answers 401 before anything is parsed | `providers/cashfree.py::verify_webhook` |
| Replay of old webhooks | signature timestamp must be within -5 min .. `CASHFREE_WEBHOOK_MAX_AGE_HOURS` (72 h) | same |
| Duplicate delivery | SHA-256 of the raw body is stored (unique `event_hash`); a processed repeat answers 200 `duplicate`. The table stores no signature and no body | `payments.py::handle_webhook`, `internship_payment_webhooks` |
| Double-recording one payment | partial **unique index** `uq_payment_provider_payment (provider, provider_payment_id)`; one receipt per transaction (`FinancialDocument.transaction_id` unique); row lock on the order in the webhook and scheduled paths | migration 0099/0100 |
| Wrong amount or currency | success is accepted only for the order's exact amount and currency, otherwise `payment_mismatch` is recorded for staff | `apply_gateway_payment` |
| Amount tampering | the amount is decided on the server from the fee the student accepted; the browser never supplies it | `start_checkout` |
| Money from non-success states | FAILED, USER_DROPPED, CANCELLED, VOID, PENDING, NOT_ATTEMPTED never confirm; a late failure cannot flip a confirmed payment (`order.status` flips to `failed` only from `active`; the same payment id answers `already recorded`) | `STATUS` map, `apply_gateway_payment` |
| Accidental live mode | three independent switches: `CASHFREE_ENABLED`, `CASHFREE_ENV=production`, `CASHFREE_ALLOW_PRODUCTION=true`; the adapter refuses production without the last | `CashfreeProvider.__init__` |
| Secret exposure | the secret key is never in `__repr__`; `payment_session_id` is excluded from the audit table; staging scripts never print secrets | provider, model |
| Refund safety | one open refund per payment (409), a deterministic refund id from the refund row, amounts capped at what is left, credit notes issued once | refund service; tests |
| Unauthenticated surface | the webhook is rate-limited (300/min per IP) with a 64 KB body cap; student endpoints need the onboarding token and are rate-limited | `routes.py` |

**Reconciliation specifics (this PR).** Only a verified SUCCESS for the exact amount and currency confirms; the new code only widens
*which orders are asked about*, never *what counts as paid*. Cost is bounded: at most one Cashfree request per order per 10 minutes,
on the 15-minute tick, for at most about 90 minutes after creation (30-minute order life plus the 60-minute grace), so about six
requests per abandoned order. After the window an order is final and Cashfree is not asked again (a signed notification can still record a
late payment). The 60-minute grace is a judgement, not a Cashfree figure.

**Findings from this review (none blocks release):**

| # | Severity | Finding | Why it is not a blocker |
|---|---|---|---|
| L1 | Low | A webhook and a student's status check recording the same payment at the same instant: the loser hits the unique index and gets an error (500 on that request) | No duplicate is possible; the retry (Cashfree's, or the student's second press) sees `already recorded` |
| L2 | Low | An auto-refund notification with no matching payment is logged and stored in the webhook table but not surfaced to finance | Rare; the money state is Cashfree's, and the table keeps the event |
| L3 | Cosmetic | A re-wrapped (different bytes) copy of an auto-refund notification adds a second timeline line; a late failed notification adds a "payment failed" line to an already paid timeline | No ledger effect |
| L4 | Design | A student who starts a **fresh** order while the old Cashfree order is still payable could pay twice | Existing overpayment handling applies; unchanged by this PR |
| L5 | Operational | With `CASHFREE_ENABLED=false` the webhook answers 503 and reconciliation does nothing, so payments made while it is off are not recorded automatically | See the rollback procedure in section 5 |

---

## 3. Celery / Kombu / redis-py pins and the production image rebuild risk

**What happened.** `requirements.txt` pinned `celery==5.4.0` and `redis==5.0.8` but not `kombu`. Celery 5.4.0 accepts `kombu >=5.3.4,<6.0`,
so a rebuild with a cold pip layer resolved **kombu 5.7.0**. Kombu 5.7.0 has a runtime guard (`redis.VERSION < (6, 1, 0)` raises
`VersionMismatch`) and its Redis extra needs `redis>=6.4.0`; kombu 5.6.2 and earlier do not. On staging, `celery_worker` and `celery_beat`
restarted in a loop (RestartCount 18) while the API stayed healthy (it opens no Kombu Redis connection until it publishes a task).
`pip check` cannot see it; the requirement is in a kombu extra nothing asked for. There is no lockfile.

**The fix.** The stack is pinned as one set: kombu 5.6.2 (supports `redis>=4.5.2,<6.5` excluding 5.0.2 and 4.5.5), amqp 5.4.1, billiard 4.3.1,
vine 5.1.0. Before: pip resolved kombu 5.7.0 / amqp 5.4.2 / billiard 4.3.2. After: kombu 5.6.2 / amqp 5.4.1 / billiard 4.3.1. Upgrading
redis-py to 6.x instead was not chosen: it reaches the app's own Redis clients, slowapi/limits and the OpenTelemetry instrumentation and
needs its own review. Verified in the cloud session on Python 3.12 from the final file: `pip check` clean, the compatibility check passes
with a real broker connection and fails on the broken set with the exact error, a worker and Beat stayed up, and Beat's real
`internship-onboarding-reconcile-payments` entry fired and ran. **Not verified:** a Docker image build (no daemon in the cloud session).

**The production image rebuild risk (inferred from the repo; production was not inspected).**
- `infrastructure/aws-single-host/deploy.sh` runs `docker compose -f docker-compose.prod.yml up -d --build` on the host. That builds the
  API image **on the host** from `apps/api/requirements.txt`. If the pip layer is rebuilt (requirements changed, or the host's build cache
  was pruned), an unpinned kombu resolves to the newest release and the worker, Beat and every task-publishing request break exactly as on
  staging. Existing running containers are unaffected until a rebuild.
- So: **no production image rebuild should happen from the old `requirements.txt`.** Deploying this PR (the pins) is itself the fix. If
  an urgent production deploy is needed before this PR merges, carry only the four pin lines (and the Dockerfile check) into it.
- Before the first production build with the pins, build once without cache on a non-production machine and run
  `python scripts/check_dependency_compat.py --broker redis://<host>:6379/1` inside the image. After deploy, `docker ps` must show the
  worker and Beat up with `RestartCount` 0.
- Rollback: image rollback per `docs/release/ROLLBACK_PLAN.md` (there is no schema change to roll back).

---

## 4. The production MinIO image problem and a safe resolution approach

**Facts.** `docker-compose.prod.yml` (and the dev compose file) run `image: minio/minio:latest` with a health check that calls `curl`
inside the image. During the staging work the official `minio/minio` image could not be pulled (MinIO stopped publishing community images
in October 2025; confirm on the host). The running production container keeps working. The exposure is: the host is rebuilt or the local
image is lost (`docker system prune -a`, a new instance), or the MinIO service definition changes and is recreated, and the image cannot
be fetched again. Staging uses a pinned community build (`pgsty/minio:RELEASE.2026-08-04T00-00-00Z`) and works for uploads and signed
`/_files` links, with its health check disabled because the image's tooling differs.

**Safe approach (nothing below has been executed; order matters, each step is reversible).**
1. *Read-only discovery on the host:* the running image reference and digest (`docker inspect erpx_minio`), `docker image ls --digests`,
   and `minio --version` inside the container. Record them.
2. *Preserve the exact bits that are running:* `docker save` the image, store the tarball with its checksum off the host, and push it to a
   registry the owner controls (for example a private ECR repository), then record the immutable digest.
3. *Pin without changing behaviour:* point the compose file at `<registry>/minio@sha256:<digest>`. Same bits, same data format, no
   migration. Nothing should recreate the MinIO container during the Cashfree start; do this as its own, separate change.
4. *Protect the data first:* confirm the off-host backup of `erpx_minio_data` restores (`docs/operations/offsite-backup.md`).
5. *Long term, separately planned:* choose a supported store (a maintained community build such as the one staging uses, a build from
   source at a pinned tag, or AWS S3, which means IAM, a bucket and a review of `STORAGE_PUBLIC_PREFIX`/presigning). Test the candidate
   against a **copy** of the data, including a signed `/_files` URL through Caddy (the `Host: minio:9000` signing rule), uploads and
   deletes. Keep the old pinned image and a volume snapshot for rollback.
6. *Do not:* run `docker compose pull`, `docker image prune -a` or `docker system prune -a` on the host; swap images under live data
   without the copy test; change MinIO and enable Cashfree in the same window.
Any replacement image may lack `curl`, so the health check needs adjusting (or an `mc ready local` style check) when the image changes.

---

## 5. Cashfree production configuration, secrets, webhook, domain whitelist, rollback

**Account and credentials (owner).** A production-approved Cashfree merchant account; the production **App ID** and **Secret Key** (not the
Test-mode pair). They are server secrets only: in `/opt/erpx/.env` on the host (the file `docker-compose.prod.yml` already reads; it should be root-owned with mode 600), never in git, CI output, chat,
tickets or logs. The same secret signs webhooks, so rotating it is a coordinated change (rotate in the dashboard, update the file,
recreate api/worker/beat).

**Settings (names; values are the owner's).**
| Setting | Production value |
|---|---|
| `CASHFREE_ENABLED` | `true` |
| `CASHFREE_ENV` | `production` |
| `CASHFREE_ALLOW_PRODUCTION` | `true` (**only with the owner's written authorization**) |
| `CASHFREE_APP_ID`, `CASHFREE_SECRET_KEY` | production keys |
| `CASHFREE_API_VERSION` | `2025-01-01` (the version the adapter was validated on; must match the webhook version; `2026-01-01` is untested) |
| `CASHFREE_ORDER_MINUTES` / `CASHFREE_WEBHOOK_MAX_AGE_HOURS` | defaults 30 / 72 |
| `FRONTEND_URL` | already `https://erp.pentrix.in` in `docker-compose.prod.yml` (the checkout return URL is built from it) |

**A production compose change is required and is not part of this PR.** `docker-compose.prod.yml` states that only variables listed in
`x-backend-env` reach the containers, and no `CASHFREE_*` name is listed. Adding them (as `${NAME:-default}` pass-throughs) is a separate,
owner-approved change; api, worker and Beat share that block, so all three are recreated by it.

**Webhook (Cashfree dashboard, Production mode; environments are configured separately from Sandbox).**
- URL: `https://erp.pentrix.in/api/v1/public/payments/cashfree/webhook` (Caddy already proxies `/api/*` for that host; no IP allow-list is
  needed, the signature authenticates the call).
- Version `2025-01-01`. Events: payment success, payment failed, payment user dropped, refund status, and auto refund status if offered.
- Delivery: Cashfree retries non-200 answers (per its documentation excerpts the default is three retries at 2, 10 and 30 minutes; check the dashboard). ERPX answers 200 for processed,
  duplicate and unmatched events, 401 for a bad signature, 400 for an unreadable body, 413 above 64 KB, and 503 only when Cashfree is not
  enabled or not configured.
- Domain whitelist: add `erp.pentrix.in` where the dashboard asks for approved domains. If the account has **API IP whitelisting**
  enabled, the host's public egress IP must be listed (I could not verify this setting from here; check it).

**Per-internship switch.** Finance enables the method "Online (Cashfree)" for one internship at a time; nothing is offered while it is off.

**Rollback procedures.**
1. *Stop new checkouts first, not the plumbing.* Remove "Online (Cashfree)" from the internship's methods. **Leave `CASHFREE_ENABLED=true`
   and the webhook enabled** so payments already in flight are still recorded (L5): with the master switch off the webhook answers 503 and
   reconciliation does nothing, and Cashfree gives up after its retries.
2. Wait until no Cashfree order is open (order life 30 min + 60 min grace) and `recon`-style checks show nothing pending, then turn
   `CASHFREE_ENABLED=false` (recreate api/worker/beat). Disable the production webhook endpoint in the dashboard last.
3. If anything was paid while the master switch was off, or after the grace window, reconcile by hand from the Cashfree dashboard
   (orders older than the window are not re-asked automatically) and record each payment through finance; never edit or delete ledger rows,
   corrections are new rows.
4. Application rollback: image rollback per `docs/release/ROLLBACK_PLAN.md`; this PR has no migration.
5. Refunds: pending Cashfree refunds are still reconciled while the master switch is on; do not disable it with refunds pending.

---

## 6. Release blockers versus accepted limitations

**Release blockers (approvals, configuration and process; none is a code defect):**
| # | Blocker | Owner |
|---|---|---|
| B1 | Independent review of this PR (no review is recorded) and the owner's merge; only the owner merges and deploys (`docs/team-workflow.md`) | reviewer, owner |
| B2 | **CI has not run on this PR and will not:** `ci.yml` triggers on `main`/`develop` and the repository has only `master` (a branch `srujan/ci-run-on-master` exists, not reviewed here). Everything reported comes from the author's cloud runs. Run the suite in CI or on the owner's machine before merge | owner |
| B3 | The Celery pins must be in any production image build; no rebuild from the old file | owner |
| B4 | The `CASHFREE_*` pass-through added to `docker-compose.prod.yml` (separate change) and the production secrets placed in `/opt/erpx/.env` | owner |
| B5 | Production keys, webhook registration (URL, version, events), domain whitelist, and API IP whitelist if enabled | owner |
| B6 | Written authorization before `CASHFREE_ALLOW_PRODUCTION=true` | owner |
| B7 | MinIO: at least steps 1-3 of section 4 (preserve and pin the running image) before any rebuild or recreate of that host | owner |
| B8 | The owner's decision on a controlled start, a named rollback owner and on-call | owner |

**Accepted limitations (documented, not blockers):**
- A genuine `PAYMENT_USER_DROPPED_WEBHOOK` was **not observed** (row 6a). Cashfree documents it; nothing found says the sandbox emits it; the handler is covered by synthetic payloads. ERPX never marks Paid from a dropped event.
- Row 10 is **partially verified**: the failed attempt was detected automatically on real Cashfree; the successful retry on the same order and its automatic recovery were not observed (no accessible retry path in the checkout as used). Covered by 18 automated cases.
- An auto-refund notification (mocked body only); API version `2026-01-01`; the unexplained stuck return page on the first checkout (row 8, no code change); the cancelled-checkout check is manual only (most likely closed before a method was chosen, which creates no attempt and no notification); the scheduled reconciliation has one real run (row 9); the 60-minute grace is a judgement; the attributions in rows 7, 7b and 7c are "likely, not proven" as marked.
- Not run anywhere by the author: a Docker image build, real bash 3.2, a production-mode Cashfree call.

---

## 7. Controlled production start: checklist (not executed)

Nothing below has been run. Each step needs the owner's go-ahead and is recorded when done.

**A. Before anything touches production**
- [ ] PR #163 independently reviewed; findings answered; CI (or an owner-run full test pass) green on this branch (B1, B2).
- [ ] Owner merges; a release note says what is in it (reconciliation fix, auto-refund handling, Celery pins, no migration).
- [ ] A fresh, restorable backup of the database and of `erpx_minio_data` exists and a restore has been rehearsed (`docs/operations/disaster-recovery-runbook.md`).
- [ ] MinIO running image preserved and pinned (section 4, steps 1-3) (B7).
- [ ] A named rollback owner and on-call for the first day (B8).

**B. Build and deploy the code with Cashfree still OFF**
- [ ] Build the API image without cache on a non-production machine; run `check_dependency_compat.py --broker ...` in it (section 3).
- [ ] Deploy through the documented release process (`docs/release/DEPLOYMENT.md`, then `SMOKE_TEST.md`). Confirm api, worker and Beat are up with `RestartCount` 0 and that Beat's reconciliation entry runs (`{'checked': 0, 'confirmed': 0}` with the flag off).
- [ ] Confirm `CASHFREE_ENABLED` is unset/false: the webhook answers 503, "Online (Cashfree)" is not offered.

**C. Configuration**
- [ ] Owner-approved change adds the `CASHFREE_*` pass-throughs to `docker-compose.prod.yml` (B4).
- [ ] Production keys placed in `/opt/erpx/.env` (root, 600), not echoed anywhere.
- [ ] Cashfree dashboard (Production): webhook URL, version `2025-01-01`, events, domain whitelist, API IP whitelist if enabled (B5).
- [ ] Written authorization recorded (B6).

**D. Switch on, in this order, one step at a time**
- [ ] Set `CASHFREE_ENABLED=true`, `CASHFREE_ENV=production`, `CASHFREE_ALLOW_PRODUCTION=true`; recreate api, worker and Beat; confirm they are healthy and an **unsigned** webhook call answers 401 (the endpoint is live and rejecting).
- [ ] Finance enables "Online (Cashfree)" on **one** internship only.

**E. First real transaction (staff member, smallest sensible amount)**
- [ ] The staff member pays; confirm the signed webhook arrives (dashboard Logs: 200), the order becomes `paid`, one receipt, one email, the five integrity checks are zero (`docs/CASHFREE_SANDBOX.md` evidence queries), no accounting entries.
- [ ] Refund that payment from the finance screen; confirm the refund webhook, the credit note and the net figures.
- [ ] Watch the next reconciliation ticks: nothing unexpected is "confirmed" or "mismatched".

**F. Widen carefully**
- [ ] Open to students only after E is clean; review the first day's webhook logs, `payment_mismatch` events and any auto-refund notices.
- [ ] Keep the rollback of section 5 at hand; add further internships one at a time.

**Abort criteria:** a duplicate payment, receipt or email; a `payment_mismatch`; a webhook with a valid signature that is not recorded; any Celery container restarting; a student charged but shown unpaid for longer than the reconciliation window. Stop new checkouts (section 5, step 1) and investigate before continuing.

---

## 8. Are there release-blocking defects in the code?

**No release-blocking defect was found in the code under review.** The remaining blockers (section 6) are approvals, configuration and
process. The review covered the full diff against `master`, the webhook verification, the confirmation and refund paths, the database
constraints, and the production guards. What that does and does not establish:
- It is the author's own review plus automated tests (407 unit and 76 API tests pass; the 18 new cases fail on the original code), so an
  independent review (B1) is still required and is the main remaining control.
- The low-severity findings L1-L5 are real but do not endanger money; L5 is a procedure, covered in section 5.
- Two process defects are outside the payment code: CI does not run on `master` pull requests (B2), and the production image build could
  silently regress without the pins (B3). Both are named above.
- Behaviours that only a production-mode run can show (live webhook delivery from Cashfree's production environment, the real card/UPI
  flows) have by definition not been tested, which is why section 7 starts with one staff transaction.
