# Release checklist: internship onboarding (PR #161)

Production today: migration `0097` (Bulk Download, #160). This release adds `0098`, `0099`, `0100` (additive only).
Run by the owner on `i-0054474b85332980a` through Run Command, one step at a time, never between 01:45 and 04:30 UTC
(in-app dump 02:00, off-server backup 03:30). Each script refuses to run in the wrong state and never rolls back by itself.

## 0. Before the window (no production change)

- [ ] Owner approves the exact merge commit of PR #161 (40-character SHA). Re-check the PR's head SHA and that `master`
      has no new migration after `0097`; if it does, stop: `0098`-`0100` must be renumbered on the branch first.
- [ ] PR merged by the owner (branch protection respected; signed commits verified).
- [ ] Production environment unchanged for this release: `CASHFREE_ENABLED` unset/false, `CASHFREE_ALLOW_PRODUCTION`
      unset/false, no Cashfree keys; `CLAMAV_ENABLED` unset/false. No other variable is needed.
- [ ] Last nightly off-server backup (03:30 UTC) reported success; at least 4 GB free on the instance.
- [ ] Owner decisions for the first internship to use it are ready (see "Configuration still needing the owner").

## 1. Source: `01_source.sh` (no container touched)

- [ ] Set `SHA`. Expect: `alembic now: 0097 (head)`, the three migration files present, `/opt/erpx` at `SHA`.

## 2a. API and migrations: `02a_deploy_api.sh` (checkpoint C1)

Takes, before any change: `pg_dump -Fc` of `erpx` to `/opt/backups/pre-release/erpx-before-0100-<TS>.dump` (listed with
`pg_restore --list` as proof it is readable) and the running api image id in `/opt/backups/pre-release/images-0100.env`.
Then rebuilds only `api`; starting it runs `alembic upgrade head`: `0097 -> 0098 -> 0099 -> 0100`.

C1, all must hold:
- [ ] api healthy; `alembic: 0100 (head)`; health endpoint answers.
- [ ] `onboarding tables: 12`; `bulk_export_jobs kept: 1`; `storage tables kept: 2`.
- [ ] `onboarding permissions: 3`; `document safety columns: 3`.
- [ ] `cashfree enabled: False env: sandbox production allowed: False`; `virus scanning enabled: False`.
- [ ] `BACKUP_FORMAT` and `BACKUP_IN_APP_SCHEDULE_ENABLED` as before; no new errors in the api log.
- If C1 fails: `99_rollback.sh` with `MODE=api` (downgrade `0100 -> 0097`, then the saved image).

## 2b. Worker and beat: `02b_deploy_worker_beat.sh` (checkpoint C2)

- [ ] Worker healthy and answers ping; `worker knows the onboarding tasks: 5`.
- [ ] Beat has `internship-onboarding-sweep` and `internship-onboarding-reconcile-payments`; `bulk-exports-cleanup` and
      `backups-trigger-daily` kept; backup settings unchanged.
- If C2 fails: `MODE=workers`.

## 3. Web: `03_deploy_web.sh` (checkpoint C3)

- [ ] Web healthy; bundle contains "Student self-service onboarding"; site answers.
- If C3 fails: `MODE=web`.

## 4. Acceptance on real MinIO (plain Administrator, not Super Admin; one test student with a mailbox you control)

- [ ] Existing internships unchanged: Our Internships > Onboarding shows "Off" (manual) until configured.
- [ ] Configure one internship: hybrid; bank transfer and/or UPI only (Cashfree shows "not set up"); fee (defaults to
      INR 2,000); the refund policy wording; documents without identity documents (they are refused until ClamAV
      exists); closing date; issuer legal name/address as decided. Save succeeds.
- [ ] Send the test student their link; the email arrives; the link opens on a phone; the token disappears from the
      address bar.
- [ ] Student: save and resume, upload a PDF and a JPG/PNG, accept (the refund policy is shown above the agreement),
      submit a bank/UPI claim with a proof image.
- [ ] MinIO: the uploads exist under `onboarding/<org>/<application>/` in the production bucket; staff preview opens
      through a short-lived link and expires; the payment proof opens from Payment checks.
- [ ] Finance user confirms the claim -> the student shows paid; a receipt PDF (`RCPT-...`, issuer as configured, no
      GSTIN, no tax lines) opens for staff and student; the receipt email arrives.
- [ ] Reviewer verifies the documents -> completion page with next steps; LMS access as configured.
- [ ] Bulk Download of the onboarding documents produces a ZIP that opens.
- [ ] Storage Manager still lists `backups/` as protected; existing files still open.
- [ ] If a refund is tested: bank/UPI refund with transfer reference -> credit note; a second refund of the same payment
      while one is open is refused.
- [ ] Clean up the test student's data only through the application (cancel onboarding); nothing is deleted by hand.

## Rollback

- `99_rollback.sh`, one `MODE` only (`web`, `workers`, `api`), restores the images saved in
  `/opt/backups/pre-release/images-0100.env`. `MODE=api` downgrades `0100 -> 0097` first, dropping only the onboarding
  tables; `bulk_export_jobs`, the Storage Manager tables and every other table stay.
- Export `payments.csv` and the financial documents list first if any real money was recorded.
- Uploaded onboarding files and receipts stay in the bucket under `onboarding/` (nothing is deleted).
- The pre-release dump is a last resort that needs its own approval (restoring it discards everything written since).
- Verified locally with data: `0100 -> 0097 -> 0100`; Storage Manager and Bulk Download rows byte-identical.

## Must stay off in this release

Cashfree (`CASHFREE_ENABLED`), installment plans (not built), automatic deletion of identity documents (not built),
tax invoices (only appear once finance enters a GSTIN and tax treatment; do not enter them until verified), posting to
the accounting module (not built), identity documents such as Aadhaar (refused until `CLAMAV_ENABLED` with a running
clamd; the setting must not be switched on without the service).

## Configuration still needing the owner

| Item | Needed before | Default if not given |
|---|---|---|
| Refund policy wording | any internship where students pay through their link | saving such settings is refused |
| Issuer address / footer (legal name defaults to GIR Technologies) | first receipt | receipt shows the legal name only |
| Bank account and/or UPI ID per internship | collecting payments | payment methods cannot be enabled |
| Fee per internship if not INR 2,000 | sending links | INR 2,000 |
| GSTIN, tax treatment and rate (verified) | any tax invoice | receipts only, no tax shown |
| ClamAV service (host, port) | collecting identity documents | identity documents refused |
| Identity-document retention period (days) | collecting identity documents | saving such settings is refused |
| Cashfree sandbox access and keys, then production authorization | online payment | off |
| Accounting posting, installments | later releases | not available |
