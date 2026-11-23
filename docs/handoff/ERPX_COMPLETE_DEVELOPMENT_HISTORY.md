# ERPX: complete development history of the Claude Code Cloud engagement

Covers 2026-10-30 (first Cloud session) to 2026-11-03 (this handoff). Repository `connect112/ERPX`.

## 0. How to read this document (provenance)

Every statement is tagged by where it comes from. **Do not treat anything tagged OWNER or UNVERIFIED as independently confirmed.**

| Tag | Meaning |
|---|---|
| GIT | Verified from commits, branches or file contents in the repository. |
| GH | Verified from the GitHub API (PR bodies, states, CI runs) at the time of writing. |
| OWNER | Reported by the owner (Srujan) in the conversation; the Cloud session could not observe it (production, the owner's Mac, Cashfree dashboard). |
| CLOUD | Observed by the Cloud session in its own container (local throwaway PostgreSQL/Redis, test runs). |
| UNVERIFIED | A hypothesis or recollection that nothing recorded confirms. |

Sources used: `git log` of `master` and the three feature branches; the GitHub API for PRs #157 to #164 and CI runs #7, #8, #10, #11;
the repository documents; and the Cloud session's own transcript (the owner's 48 instructions, in order). The Cloud session was
compacted twice, so some intermediate reasoning is only known through summaries; anything not recoverable is left out rather than invented.

The Cloud container is gone after this session. Its scratch files (virtualenvs, a throwaway PostgreSQL with databases
`erpx_ci_probe`, `erpx_fresh`, `erpx_fresh2`, Redis on port 6391, extracted logs) were never in the repository and are lost.

## 1. Baseline before the Cloud engagement (OWNER, from the first instruction of 2026-10-30)

- Production release commit named by the owner: `28b5b642f3b1027695e4fcff7861a703337c8a37` (this is the merge of PR #157).
- Stage 3 backup archival and cleanup complete; Stages 4 and 5 (backup safeguards, Storage Manager) and the backend security updates merged and deployed; production database at migration `0096`; API, Celery worker, beat and web checkpoints passed; Storage Manager initial Administrator checks passed.
- Open items the owner listed: the superuser Trash/Restore acceptance (postponed) and confirmation that the next scheduled S3 backup writes `manifest.json` and `SHA256SUMS`.
- The owner's previous workflow was local Claude Code; the handoff for the Cloud move was PR #158 (`srujan/cloud-handoff`, `docs/CLOUD_HANDOFF.md`, `docs/CLOUD_STARTER_PROMPT.md`).
- Repository structure (GIT): FastAPI backend `apps/api` (app code under `apps/api/app`), domain modules under `modules/`, shared code under `packages/`, React front ends `apps/web` (admin, erp.pentrix.in), `apps/student-portal`, `apps/trainer-portal`, `apps/corporate-portal`, tests under `tests/`, ops scripts under `ops/`, AWS single-host deployment under `infrastructure/aws-single-host/`. Only one long-lived branch: `master`.

## 2. Chronology

### 2.1 2026-10-30: Universal Bulk Download (PR #159 → #160)

- Instruction 1 (OWNER): build a production-ready, reusable bulk document download (selected and all-filtered, ZIP, Celery for large exports, progress and failures, reuse existing generators) for certificates, offer letters, completion certificates and other document modules.
- Built as `modules/bulk_exports` with a small `DocumentSource` adapter per module and migration `0097_bulk_export_jobs` (GIT; PR #159 body GH).
- Reviews (instructions 2 to 6): migration 0097 up/down/up on an isolated database; rollback promise checked with Storage Manager rows present (rows survive a downgrade to 0096); real-MinIO compatibility could not be tested in the Cloud (MinIO cannot be downloaded there), so an S3 stand-in (`moto`) was used and the post-deploy real-MinIO check was left in `docs/CLOUD_HANDOFF.md` section 12.
- Signing problem: 9 of 10 commits in #159 were "Verified" on GitHub; the old handoff commit `f2c618a` was not. Resolution without losing work: new PR #160 with two signed commits whose tree is identical to the tested release candidate `bc00b83` (`ddadcfc` the feature, `ad79b0f` the handoff). Merged 2026-10-30 as `958d346`. #158 and #159 were left open on purpose (GH, still open drafts).

### 2.2 2026-10-30 to 2026-11-01: Automated internship onboarding (PR #161)

- Instruction 7 (OWNER, "master development prompt"): extend Our Internships with automated, manual and hybrid onboarding: secure student links, deadlines and extensions, optional late fees, custom forms and document requirements, digital offer acceptance, **Cashfree** payments, manual bank/UPI verification, receipts/invoices/credit notes, refunds, LMS access, reminders and exports. Not a new application: it builds on the existing lifecycle (institution → workshop → hackathon → evaluation → selection → offer letter → acceptance → documents → verification → payment → completion → LMS → training → certification).
- Built on branch `claude/internship-onboarding` in milestones (GIT commit subjects): `f0e9992` audit/architecture/fee maths; `62fb2e5` derived status machine; `6016530` settings, templates, links, student API, document review; `4875cfc` shared-file wiring; **`b05a84a` ledger, bank/UPI verification and the Cashfree adapter**; `06dab8d` settings and beat entry; `85b5091` screens; `75eaec4` completion and LMS access; `b305d30` receipts, tax invoices, credit notes, refunds, cancellation; `1abbb0f` bulk download of onboarding documents; hardening (`2ad6c38`, `4bac2ca`, `a0c15a7` optional ClamAV scanning off by default); release scripts `6c0442b` and checklist `7b053ec` (production 0097 → 0100).
- Migrations `0098_internship_onboarding`, `0099_internship_payments`, `0100_internship_financial_documents` (GIT). Checkpoint C1 expects 13 onboarding tables.
- Instruction 14 (OWNER): prepare the release; keep Cashfree, installment plans and automatic deletion of identity documents off.
- 2026-11-01, instruction 15 (OWNER): the Cashfree merchant account for GIR Technologies (OPC) Pvt. Ltd. was activated. Review the adapter against Cashfree's published API, document dashboard steps, make the INR 2,000 amount come from the internship's configured fee, trigger receipts and LMS eligibility only after authoritative payment verification. Result (GIT): `04928fa` contract notes, fee/authority tests and opt-in sandbox tests; `09f3c6e` API version default `2025-01-01`; `39654ab` sandbox guide (`docs/CASHFREE_SANDBOX.md` sections 1 to 3).
- Instruction 16 (OWNER): per-internship "Allow Refund Requests" switch (default off, policy wording required when on, exact accepted version recorded) and saved bank/UPI payment accounts (finance-verified, masked, audited, UPI QR for the amount owed). Result (GIT): `68e827c`, `0b58175`, `520ac97` (head of #161).
- Instruction 17 (OWNER): authorized a controlled production deployment of #161 with preflight, merge after review, then AWS Systems Manager release scripts. **The Cloud session stopped at Phase 2 (CLOUD, transcript):** GitHub required an independent review (the PR author cannot approve their own PR) and the session had no working AWS access (the keys in its environment were rejected, `erp.pentrix.in` was blocked). Nothing was merged or deployed by the Cloud session.
- PR #161 was merged by the owner on 2026-11-01T15:09:47Z as `86e4a86` (GH). The owner then wrote that **the current production commit is `86e4a86334eb60015f713c059bf406bdb2ca015c`** (OWNER, instruction 18). How the release scripts ran in AWS, and the state of production migrations after that, are not recorded in the repository: ask the owner (UNVERIFIED by the Cloud session).

### 2.3 2026-11-01: UI separation (PR #162) and the start of PR #163

- Instruction 18 (OWNER): pause Email Studio entirely; split the Our Internships onboarding screen into two tabs (Onboarding / Onboarding Settings); validate Cashfree in the sandbox.
- UI separation → draft **PR #162**, branch `claude/onboarding-settings-tab`, head `62d661125f9b23b85f68e6e3dae7f7bbb97a3659`: web files `flow-panel.tsx` split, `lib/tabs.ts` rules, backend `service.py` read-only permission flags; no migration. Reported verification (GH body): `tsc` clean, eslint 0 errors, vitest 200 passed, 103 onboarding tests, 24 browser checks as a plain Administrator. Still an unreviewed draft.
- Cashfree sandbox validation → **PR #163**, branch `claude/cashfree-sandbox-readiness`: first commits `9f3b70f` (acknowledge `AUTO_REFUND*` notifications and report them to staff instead of refusing with 400) and `f26fbdf` (isolated staging kit and assessment). The Cloud session reported (CLOUD, transcript 2026-11-01 17:34) that it could not reach Cashfree, had no sandbox keys and had no staging environment to receive webhooks, so it stopped before any live sandbox test; the sandbox tests were run by the owner on a Mac staging stack (below). Note: the Cloud session's designated branch `claude/pensive-wozniak-81byk7` is the head (`bc00b83`) of the still-open PR #159, which the owner asked to preserve; none of the later work was committed to it.

### 2.4 2026-11-02: Isolated Mac staging stack

- Instruction 19 (OWNER): harden the staging kit before running it on a MacBook Pro M3 Pro (bind only needed ports, isolate from other projects' containers and networks). Result: `e01cba4` (`ops/staging-cashfree`: self-contained Compose stack with PostgreSQL, Redis, MinIO (pinned community build `pgsty/minio:RELEASE.2026-08-04T00-00-00Z`), Mailpit, nginx gateway, web, tunnel; `staging.sh`, `preflight.sh`, evidence SQL).
- Instruction 20 (OWNER): the API container restarted with `NoReferencedTableError: Foreign key associated with column 'organizations.default_…'`. Cause (GIT, `6833ccd`): the standalone bootstrap seed `apps/api/scripts/seed.py` did not import two models that `Organization`'s foreign keys point at. Fix: register them. `8c24113`: web health check asks `127.0.0.1`.
- Instruction 21 (OWNER): two successful ₹2,000 sandbox payments, webhooks 200, receipts, replay, ₹1 refund and credit note had passed. Open list: replay audit, failed payment, cancelled/dropped, lost webhook, the stuck return page, the ₹1 refund ledger audit, refund idempotency, fix the macOS preflight, a dedicated Docker subnet, update the report. Result (GIT): `6090ec8` acceptance tests (replays, one-rupee refund, reconciliation); `350976c` dedicated subnet, allowlist from the example, evidence, persistent mail; `a8fbd3c` acceptance record, return-page analysis, rollout prerequisites.

### 2.5 2026-11-03: Acceptance testing, defects found, CI

Commits in order (GIT), with the reason each existed:

| Commit | Reason |
|---|---|
| `87f63fe` | `preflight.sh` line 46 broke on macOS bash 3.2 (malformed case pattern in the allowlist command substitution). The Cloud session had bash 5.2 and could not see it; the owner ran it on the Mac. |
| `0127749` | Record Mac evidence for replays and the one-rupee refund. |
| `fbad8c4` | Compose tried to rebuild the occupied staging network (subnet `10.253.247.0/24`, running containers). Fix: the staging network is external and managed by `staging.sh`. |
| `8c87209`, `0e76d83` | Record failed, cancelled and lost-webhook results; the lost-webhook recovery is most likely the return page (not proof). |
| `7ec66e9`, `4346b01` | `staging.sh gate on/off/status` isolates the "I have paid: check status" button by refusing the webhook and the return-page check at the gateway; record Student E's pass. |
| `c44f5bb`, `061e786`, `a210098` | `staging.sh recon` mode to let the scheduled reconciliation be the only recovery path; readiness-check bug fixes (the first run said the worker did not list the task although Beat had dispatched it); remove a clock dependence from a test. |
| `847bcee` | Record row 9 (scheduled reconciliation) PASSED, Student F. |
| `c10e867` | **Defect fix in payment code**: reconcile `failed` orders and recently `expired` ones (see the Cashfree document, section 5). |
| `6d2806c` | **Celery crash fix**: pin the Celery messaging stack and add a compatibility check (see below). |
| `ba48128` | Record row 10 as PARTIALLY VERIFIED (Student G). |
| `c4b4c1d` | Final review handoff for PR #163 (`docs/CASHFREE_REVIEW_HANDOFF.md`). |
| `f386fca`, `b9852ff`, `d96b976` | CI: trigger on `master`; `PYTHONPATH` for the migration step; record real CI results in the handoff. |

Key discoveries, in the order they happened:

1. **Mac `recon check` readiness failures** (instructions 32 to 35, OWNER): the checker reported the worker did not list the reconciliation task even though Beat dispatched `internship_onboarding.reconcile_payments` at 09:00 and 09:15 UTC and the worker succeeded. The Cloud session found checker bugs and a clock-dependent test; fixed in `061e786`, `a210098`.
2. **Row 9 passed (OWNER, instruction 36):** Student F `ERPX-INT-2026-000009`, payment confirmed at 10:15:00 UTC by the scheduled task with the webhook (503), return page and student status check all blocked.
3. **USER_DROPPED investigation (instruction 37):** while studying Cashfree's documentation for `PAYMENT_USER_DROPPED_WEBHOOK`, probe tests against PostgreSQL (CLOUD) showed a **reconciliation gap**: a failed or dropped attempt set the local order to `failed`, but a Cashfree order keeps taking attempts until it expires; if the later success notification was lost, the scheduled task (which only checked `active` orders) checked nothing. Money was not lost (Cashfree held it) but ERPX showed the student unpaid. Fixed in `c10e867` with the owner's approval (instruction 38: "approved for development and testing, not for deployment").
4. **Celery worker and Beat crash loop (instructions 39 and 40, OWNER):** after rebuilding the staging API image, both Celery containers restarted (ExitCode=1, OOMKilled=false, RestartCount=18) with `kombu.exceptions.VersionMismatch: Redis transport requires redis-py versions 6.1.0 or later. You have 5.0.8.` Root cause (CLOUD + OWNER logs): `apps/api/requirements.txt` pinned `celery==5.4.0` and `redis==5.0.8` but not `kombu`; Celery 5.4.0 accepts `kombu>=5.3.4,<6.0`, so a cold pip layer resolved `kombu 5.7.0`, which requires redis-py ≥ 6.1.0 (its `redis` extra says ≥ 6.4.0). The API stayed healthy because it does not open a Kombu Redis connection until it publishes a task. `pip check` could not see it because the requirement lives in a Kombu *extra* nothing asked for. Fix (`6d2806c`): pin the set `kombu==5.6.2`, `amqp==5.4.1`, `billiard==4.3.1`, `vine==5.1.0` (Celery 5.4.0 and redis 5.0.8 unchanged); new `apps/api/scripts/check_dependency_compat.py` (offline requirement check including the `kombu[redis]`/`celery[redis]` extras; `--broker URL` opens a real Kombu connection); the Docker builder stage runs it after `pip install`; CI runs it against its Redis service; 12 tests in `tests/unit/test_dependency_compat.py`; README troubleshooting entry. The owner's constraints for this fix: do not use the Mac path `~/erpx-cf-staging` (the real path is `~/erpx-cashfree-staging/ops/staging-cashfree`), do not modify Cashfree payment logic, remove staging data, delete volumes, merge, deploy or touch production. **Production implication (GIT, inferred, not inspected):** `infrastructure/aws-single-host/deploy.sh` builds the image on the host (`docker compose up -d --build`), so a cold pip layer there would have resolved kombu 5.7.0 the same way until the pins are merged.
5. **Row 10 (instruction 41, OWNER):** Student G `ERPX-INT-2026-000010`, Cashfree order `ERPXIFBE8D1204F036125239A17FF`: the first attempt FAILED and the 12:00 UTC scheduled run returned `{'checked': 1, 'confirmed': 0}` with the order `failed`; the successful second attempt was not made because the checkout offered no accessible retry path. **Partially verified.** The owner closed manual sandbox testing on 2026-11-03 (instruction 42) accepting this, and asked for the review handoff (`c4b4c1d`).

### 2.6 2026-11-03: CI investigation (instructions 43 to 46) and PR #164

Detailed in `ERPX_CI_REPAIR_HANDOFF.md`. Summary: CI had never run for `master` pull requests; after fixing triggers and `PYTHONPATH`, the full backend suite had 79 problems on a fresh database, all classified (51 missing MinIO, 27 un-seeded RBAC role in test modules, 1 stale migration-head assertion); PR #164 fixes those plus one order-dependent test; the last CI run (#11) shows `2 failed, 2204 passed, 6 skipped`, the 2 being PostgreSQL restore tests, plus the pip-audit and npm-audit gates red from dependency advisories.

The owner interrupted a tool call at the end of that work ("Request interrupted by user for tool use") and then asked for this handoff. No further CI change was made after commit `827385c`.

## 3. Failed or abandoned approaches (so nobody repeats them)

| Attempt | Why it failed |
|---|---|
| Ending the lost-webhook test by closing the Cashfree tab | Cashfree redirects to the return URL on its own, and ERPX's return page triggers an automatic status check, so recovery happened before the button could be tested (Student D, row 7c). Replaced by the gate (`staging.sh gate`). |
| Testing the manual button without a gate | Same cause. |
| Row 10 retry on the same Cashfree order | The checkout redirected to the deliberately blocked return page and the visible UI had no retry path; recorded as not observed. |
| Python 3.13 scratch virtualenvs in the Cloud | `asyncpg` and `psycopg2` would not build; rebuilt on Python 3.12 (the project's version). |
| Running the whole suite against an S3 stand-in (`moto`) as proof for MinIO | Useful for diagnosis (49 tests passed) but not equivalent: `test_integrations` (health endpoint) and `test_storage_public_urls` (signature enforcement) are MinIO-specific. Real MinIO was proven only by the CI run. |
| Reading GitHub Actions logs from the Cloud | The blob host (`*.blob.core.windows.net`) is blocked by the Cloud proxy; `WebFetch` also failed. The log tool returns only the tail, which is dominated by PostgreSQL service-container noise; only `tail_lines` ≈ 700 saved to a file and filtered reached the pytest summary. |
| OSV.dev, GitHub advisory pages | Blocked from the Cloud, so advisory severities and the zod 3.x scope could not be read there. |
| Pulling PostgreSQL 17 client binaries from Docker Hub to reproduce the restore failure | The registry rate-limited (HTTP 429). Not reproduced. |
| `pkill -f` patterns | Matched the session's own shell once; use anchored `pgrep`/PID kills. |
| Treating "identical lines" in two PRs as "merges cleanly" | The adjacent MinIO/compat-check hunks in `.github/workflows/ci.yml` do conflict (section 2.1 of the CI document). |

## 4. Implemented versus only proposed

| Item | Status |
|---|---|
| Bulk Download, onboarding, refund switch, payment accounts | Implemented, merged (#160, #161). Production status per OWNER. |
| Onboarding / Onboarding Settings tabs | Implemented, **unreviewed draft** (#162). |
| Cashfree adapter (create order, payments, refunds, webhook verify/parse) | Implemented in #161 (merged); sandbox-validated on the owner's Mac. |
| Reconciliation fix, AUTO_REFUND handling, seed fix, Celery pins and checker, staging kit, acceptance docs | Implemented in **#163 (open, not merged, not deployed)**. |
| CI trigger + `PYTHONPATH` fixes | Implemented identically in #163 and #164. |
| Hackathon fixture, migration test, team-order test, isolated MinIO | Implemented in **#164 (open)**; verified by CI run #11. |
| PostgreSQL restore-test fix | **Proposed only** (not implemented): pin the PostgreSQL client or investigate. |
| Dependency upgrades (npm: vite/vitest/happy-dom/tiptap/zod; pip: pypdf and others) | **Proposed only** (nothing changed). |
| `docker-compose.prod.yml` Cashfree pass-through, production keys, webhook registration, pinning the production MinIO image | **Proposed only**; owner decisions (see Cashfree document, section 9). |
| Offer-letter + onboarding-link email | **Not started.** No design in the repository. |

## 5. Unfinished work, in priority order

1. Independent review of PR #163 (nobody but the Cloud author has reviewed it); the owner merges.
2. PR #164: the 2 PostgreSQL restore-test failures; then resolve the `ci.yml` conflict with #163.
3. Dependency advisories (separate PRs): npm gates red in all four apps, pip-audit gate red (pypdf, 7 High).
4. Owner-only release prerequisites for Cashfree (Cashfree document, section 9).
5. PR #162 review.
6. Future: offer-letter email that carries the personal onboarding link (new branch).
