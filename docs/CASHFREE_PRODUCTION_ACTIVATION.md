# Cashfree live payments: activation guide for the ERPX production host

Works the same on an AWS EC2 instance, a Hostinger VPS, or any Linux host that runs the production Docker Compose stack.

Status of this document: **preparation only**. Nothing here has been run on a production host. Live payments stay off until the owner
authorises each step below. Companion records: `docs/CASHFREE_SANDBOX.md` (what the sandbox acceptance covered and its limits) and
`docs/CASHFREE_REVIEW_HANDOFF.md` (security review, release blockers, rollback reasoning).

Never put a key in git, a chat, a ticket, a shell command line, a remote-command feature (AWS Run Command, a control panel's "run command",
a CI job), or a log. Keys live only in `/opt/erpx/.env` (owner `root`, mode `600`). `ops/cashfree-production/cashfreectl.sh` is the one way this
guide stores them.

## 0. What the host must provide

| Need | Notes |
|---|---|
| Linux with Docker Compose v2 and bash | The commands below use `docker compose`, `bash`, `curl` and standard GNU tools. |
| The ERPX production stack in `/opt/erpx` with its `.env`, plus the shared stack (Postgres, Redis, Caddy) | The layout in `infrastructure/aws-single-host/README.md`; the folder name says AWS but nothing in it is AWS-specific. The container names used here (`erpx_api`, `erpx_celery_worker`, `erpx_celery_beat`, `shared_postgres`) come from the compose files. |
| Inbound HTTPS (443) from the internet to `erp.pentrix.in` | Cashfree's servers call the webhook; students' browsers open checkout. No source-IP rule is needed for the webhook. |
| Outbound HTTPS to `api.cashfree.com` | Used for creating orders, status checks and refunds. |
| A **fixed public IPv4** | Only needed if the Cashfree account has API IP whitelisting on (section 4). On AWS that means an Elastic IP; on a VPS, the dedicated IPv4 (confirm it will not change on a rebuild or resize). |

## 1. What the repository provides

| Piece | What it does |
|---|---|
| `docker-compose.prod.yml` (`x-backend-env`) | Passes the eight `CASHFREE_*` settings to `api`, `celery_worker` and `celery_beat` (the only services that run the app; they share that block). Every name has a safe default, so merging this changes nothing: Cashfree stays **off**, the sandbox is the default environment, and live mode needs its own switch. No other service (MinIO, the four web portals) receives them. |
| `ops/cashfree-production/cashfreectl.sh` | `status` / `keys` / `switches on` / `switches off`. Keys come from a hidden prompt and are never printed. Refuses to take keys or the live confirmation unless run at a real terminal (never piped or scripted), refuses a symbolic link, a hard-linked file or a folder other users can write to, allows one run at a time, replaces the file in one step with mode 600, and removes its temporary copy and its lock on any exit, including Ctrl-C and a kill. `switches off` needs no terminal, so it can always be used in an incident. |
| `tests/unit/test_prod_compose_cashfree.py`, `tests/unit/test_cashfreectl.py` | Guard the Compose pass-through (off by default, nothing hard-coded, no other service) and the script's rules above, using temporary files and fake keys. |

The three switches that must all be on for a live payment (a sandbox setup can never take real money by mistake):

| Name | Live value | Default |
|---|---|---|
| `CASHFREE_ENABLED` | `true` | `false` |
| `CASHFREE_ENV` | `production` | `sandbox` |
| `CASHFREE_ALLOW_PRODUCTION` | `true` | `false` |

Plus `CASHFREE_APP_ID` and `CASHFREE_SECRET_KEY` (the **Live** pair, not the Test pair). `CASHFREE_API_VERSION` stays `2025-01-01` (the version
the adapter was validated on, and it must equal the webhook version); `CASHFREE_ORDER_MINUTES=30` and `CASHFREE_WEBHOOK_MAX_AGE_HOURS=72` stay at their defaults.

## 2. Before anything touches production (all owner)

- [ ] This change reviewed and merged by the owner.
- [ ] A fresh, restorable backup of the database and `erpx_minio_data` (`docs/operations/offsite-backup.md`); the last scheduled off-server backup succeeded.
- [ ] Disk has room: `df -h /` shows at least 3 GB free. (Activation builds no image, but containers are recreated and logs grow.)
- [ ] A named rollback owner and someone on call for the first day.
- [ ] A fixed public IPv4 (section 0) if the account uses IP whitelisting.
- [ ] The production SMTP relay works: receipts and refund credit notes are emailed. Send one test through an existing flow first.
- [ ] Finance has the internship's fee, payment accounts and receipt details configured, and student phone numbers are 10-digit mobiles (checkout refuses without one).
- [ ] The owner's written go-ahead for `CASHFREE_ALLOW_PRODUCTION=true`.
- [ ] **The migration pre-check below passes.**

### Migration pre-check (do not enable payments until it prints OK)

Payments need the tables from migrations `0099` (orders, ledger, webhook log) and `0100` (receipts, invoices, credit notes). The newest revision in this repository,
`0101` (offer-letter emails), is unrelated to payments. So the deployed database must be at **`0100` or later, and at the head of the running image**:

```bash
rev=$(docker exec erpx_api alembic current 2>&1 | tail -1); echo "alembic: $rev"          # expect 0100 (head), or 0101 (head) once the offer-email release is deployed
echo "image head: $(docker exec erpx_api alembic heads 2>&1 | tail -1)"                     # must name the same revision
[[ "$rev" == *"(head)"* ]] && [ "$((10#${rev:0:4}))" -ge 100 ] && echo "migration check: OK" || echo "migration check: STOP"
docker exec shared_postgres psql -U erpx -d erpx -Atc "select to_regclass('internship_payment_orders') is not null, to_regclass('internship_payment_transactions') is not null, to_regclass('internship_payment_webhooks') is not null, to_regclass('internship_payment_accounts') is not null, to_regclass('internship_financial_documents') is not null"
```

Expected: `migration check: OK` and the last command prints `t|t|t|t|t`. Anything else is a **stop**:

- Below `0100` (for example `0097`): the payment code is deployed but its tables are not. Deploy the pending release through `docs/release/DEPLOYMENT.md` first (a separate, approved change that runs the migrations), then repeat this check.
- Not at the image's head (a database ahead of or behind the running image, for example after a rollback): fix that first; do not enable payments on a mismatch.
- `alembic` prints an error: the container is not running or not the ERPX API; investigate before going on.

Recreating `api` in the steps below runs `alembic upgrade head` with the image's own migrations, which is a no-op when this check passes.

## 3. Rollout order (one step at a time; stop at the first surprise)

All commands run on the host as root, in `/opt/erpx`. No step below builds an image or touches MinIO, Postgres, Redis or Caddy.

**Step 1: put the Compose change on the host, Cashfree still off.**
```bash
cd /opt/erpx && git pull --ff-only
docker compose -f docker-compose.prod.yml config --quiet && echo "compose ok"
docker compose -f docker-compose.prod.yml up -d --no-deps api celery_worker celery_beat    # no --build, no other service
```
`git pull` moves only the files on the host; the running images are not rebuilt, so no application code or migration changes in this step (the next normal deploy brings the rest of master).
Check: `docker ps` shows `erpx_api`, `erpx_celery_worker`, `erpx_celery_beat` up with restart count 0
(`docker inspect -f '{{.RestartCount}}' erpx_api erpx_celery_worker erpx_celery_beat`), and
```bash
docker exec erpx_api python -c "from app.core.config import settings as s; print('cashfree enabled:', s.CASHFREE_ENABLED, 'env:', s.CASHFREE_ENV, 'production allowed:', s.CASHFREE_ALLOW_PRODUCTION, 'keys set:', bool(s.CASHFREE_APP_ID), bool(s.CASHFREE_SECRET_KEY))"
curl -s -o /dev/null -w "webhook: HTTP %{http_code}\n" -X POST https://erp.pentrix.in/api/v1/public/payments/cashfree/webhook -d '{}'
```
Expected: `enabled: False env: sandbox production allowed: False keys set: False False`, and webhook `HTTP 503` (not configured; nothing is written).

**Step 2: store the keys** (still off). Use a shell that does not record what you type: an SSH session works on any host. A provider's browser console or session service
is acceptable only if you have confirmed it does not log keystrokes (on AWS Session Manager, logging to S3/CloudWatch must be off). **Never use a remote-command feature**:
its command text is kept in history, and the script refuses to run without a terminal anyway.
```bash
sudo /opt/erpx/ops/cashfree-production/cashfreectl.sh keys     # typing is hidden; nothing is printed
sudo /opt/erpx/ops/cashfree-production/cashfreectl.sh status   # keys show as <set, hidden>; mode must be 600, owner root
```
The values must be the **Live** App ID and Secret Key. Characters other than letters, digits, `_`, `-` and `.` are refused (Compose would alter them).
If a run is cut short, nothing is left half-written. If it reports another run in progress, wait for it; a lock left by a run that died is cleared automatically.

**Step 3: the dashboard, before switching on** (section 4): domain whitelist, and the IP whitelist if the account has it. Do **not** register the webhook yet.

**Step 4: switch on, and confirm the endpoint is live and rejecting.**
```bash
sudo /opt/erpx/ops/cashfree-production/cashfreectl.sh switches on        # asks you to type I AUTHORIZE LIVE PAYMENTS
cd /opt/erpx && docker compose -f docker-compose.prod.yml up -d --no-deps api celery_worker celery_beat
docker exec erpx_api python -c "from app.core.config import settings as s; print('cashfree enabled:', s.CASHFREE_ENABLED, 'env:', s.CASHFREE_ENV, 'production allowed:', s.CASHFREE_ALLOW_PRODUCTION, 'keys set:', bool(s.CASHFREE_APP_ID), bool(s.CASHFREE_SECRET_KEY))"
curl -s -o /dev/null -w "webhook: HTTP %{http_code}\n" -X POST https://erp.pentrix.in/api/v1/public/payments/cashfree/webhook -d '{}'
```
Expected: `enabled: True env: production production allowed: True keys set: True True`, and the unsigned webhook now answers **HTTP 401** (live, and rejecting forgeries).
Restart counts still 0. Within 15 minutes the worker log shows the scheduled reconciliation task succeed with nothing to do
(`docker logs --since 20m erpx_celery_worker | grep -i reconcile`); with no open orders it makes no Cashfree call. If the provider refuses to build, the log says why without printing a key.

**Step 5: register the webhook** (section 4). Registering after step 4 means Cashfree never meets a 503.

**Step 6: offer it to one internship only.** In the app, open that internship's onboarding settings, find the payment methods, and enable "Online (Cashfree)" (finance does this). The app refuses this while the server has Cashfree off, which is why it comes after step 4.

**Step 7: controlled live validation** (section 6), with a staff member and a small real amount.

**Step 8: widen** only after step 7 is clean: other internships one at a time; read the first day's webhook log and the finance screens.

## 4. Cashfree dashboard (Live mode: the toggle at the top of the merchant dashboard; Test and Live are configured separately)

**Webhook** (Developers, Webhooks, Payment Gateway, Add webhook endpoint; menu names in the dashboard may differ slightly):

| Setting | Value |
|---|---|
| Endpoint URL | `https://erp.pentrix.in/api/v1/public/payments/cashfree/webhook` |
| Webhook version | `2025-01-01` (must equal `CASHFREE_API_VERSION`) |
| Events | Payment success, Payment failed, Payment user dropped, Refund status, Auto refund status (if offered) |
| Authentication | none needed: ERPX verifies the signature (HMAC-SHA256 of timestamp + raw body, signed with the Live Secret Key) |

ERPX answers `200` for processed, duplicate and unmatched events, `401` for a bad signature, `400` for a body it cannot read, `413` above 64 KB, and
`503` only when Cashfree is switched off or unconfigured. Cashfree retries non-200 answers. A dashboard "test" ping carries no order, so
expect ERPX to answer `400` (unreadable) to it: that is not a fault; judge the endpoint by the first real payment (section 6).

**Domain whitelist** (Developers, Whitelisting, Domains): `erp.pentrix.in`. This is the only domain where a student opens checkout (the return URL is
built from `FRONTEND_URL=https://erp.pentrix.in`). `lms.pentrix.in` and the other portals do not open checkout.

**IP whitelist** (same area, if the account has API IP whitelisting turned on, which cannot be told from the repository): add the host's **public egress
IPv4**. Find it on the host with any "what is my IP" service, for example `curl -4 -s https://ifconfig.me`, and confirm it equals the A record of `erp.pentrix.in`. It applies to calls ERPX makes
(create order, status check, refund), not to webhooks Cashfree sends. Without it those calls fail with "the payment gateway refused the request (4xx)" while
webhooks still arrive. Make sure the address is fixed first (section 0), or a stop/start, resize or rebuild that changes it silently breaks checkout.

**Not needed:** an IP allow-list for Cashfree's webhook sources (the signature authenticates them), a Content-Security-Policy change (none exists; checkout loads
`https://sdk.cashfree.com/js/v3/cashfree.js`), or any change to Caddy (it already proxies `/api/*` for `erp.pentrix.in` over HTTPS).

## 5. Domain, HTTPS, callback and dependencies (verified from the repository)

- `erp.pentrix.in` is served by Caddy with automatic HTTPS; `/api/*` goes to `erpx_api:8000`; the webhook path is `/api/v1/public/payments/cashfree/webhook`.
- The checkout return URL is `https://erp.pentrix.in/internship-onboarding?order=<id>`; the return page proves nothing by itself (the server checks the status).
- The browser's checkout mode comes from the server's `CASHFREE_ENV`, so the page and the API cannot disagree.
- The app needs `httpx` (pinned in `requirements.txt`) and the pinned Celery stack (kombu 5.6.2 and friends), already in master and checked at image build. This activation rebuilds no image.
- Beat runs `internship-onboarding-reconcile-payments` every 15 minutes (asks Cashfree about open orders; does nothing while Cashfree is off). Worker and Beat get the same settings as the API.

## 6. Live validation (controlled; staff member, smallest sensible amount)

1. One internship has "Online (Cashfree)" on; a staff member (not a student) opens that internship's onboarding link and pays by UPI or card.
2. Within a minute: the order shows paid; in the Cashfree dashboard (Developers, Webhooks, Logs) the success event was delivered with `200`; exactly one receipt and one email.
3. Read-only evidence (selects only, no secrets): `docker exec -i shared_postgres psql -U erpx -d erpx < /opt/erpx/ops/staging-cashfree/evidence.sql`. Every line under `CHECKS` must be `0`.
4. Refund that payment from the finance screen. Confirm the refund webhook arrives, the refund shows confirmed (Cashfree may hold it as PENDING or ONHOLD first), one credit note is issued, and the net figures are right.
5. Watch two reconciliation ticks (30 minutes): nothing unexpected is "confirmed" or "mismatched".
6. Only then widen (step 8).

**Abort at once, and stop new checkouts (rollback step 1), if any of these happens:** a duplicate payment, receipt or email; a `payment_mismatch`; a webhook with a valid
signature that is not recorded; any of the three Celery/API containers restarting; a student charged but shown unpaid for longer than the reconciliation window (about 90 minutes).

## 7. Rollback (least disruptive first)

1. **Stop new checkouts, keep the plumbing.** Remove "Online (Cashfree)" from the internship's payment methods. Leave `CASHFREE_ENABLED=true` and the webhook registered so payments already in flight are still recorded.
2. **Wait** until no Cashfree order is open (30-minute order life plus a 60-minute grace) and nothing is pending (including refunds); the check in section 8 step 2 does this.
3. **Turn everything off:**
   ```bash
   sudo /opt/erpx/ops/cashfree-production/cashfreectl.sh switches off
   cd /opt/erpx && docker compose -f docker-compose.prod.yml up -d --no-deps api celery_worker celery_beat
   ```
   Then disable the webhook endpoint in the dashboard **last**. While `CASHFREE_ENABLED=false` the webhook answers 503 and reconciliation does nothing, so anything paid in that
   period is not recorded automatically.
4. Anything paid while it was off, or after the grace window, is reconciled by hand from the Cashfree dashboard and recorded through finance. Never edit or delete ledger rows; corrections are new rows.
5. Do not turn the master switch off while refunds are pending: they are still reconciled only while it is on.
6. If the keys may have leaked: rotate the Live Secret Key in the dashboard, run `cashfreectl.sh keys` with the new one, recreate the three services. The same secret signs webhooks, so rotate and update in the same window.
7. Code rollback is an image rollback per `docs/release/ROLLBACK_PLAN.md`; this activation has no migration.

## 8. Moving to another host (AWS EC2 to a VPS, or the reverse)

Best: **do not activate live payments and move hosts in the same window.** If the host is still undecided, move first and activate on the new host.
If payments are already live, use this order. The webhook URL and the domain whitelist name the hostname, so neither changes; the IP whitelist and the keys do.

1. **Plan the window.** Lower the DNS TTL of `erp.pentrix.in` (and the other site names) a day ahead. Name a rollback owner.
2. **Stop new checkouts and let pending payments settle.** Remove "Online (Cashfree)" from every internship, then wait until both counts are `0`:
   ```bash
   docker exec shared_postgres psql -U erpx -d erpx -Atc "select count(*) from internship_payment_orders where method='cashfree' and (status in ('created','active') or (status in ('failed','expired') and coalesce(expires_at, created_at) + interval '60 minutes' > now()))"
   docker exec shared_postgres psql -U erpx -d erpx -Atc "select count(*) from internship_payment_transactions where provider='cashfree' and kind='refund' and status='pending'"
   ```
   The first covers open orders and the 60-minute reconciliation grace; the second covers refunds still waiting on Cashfree. Do not move while either is above 0.
3. **Add the new host's fixed IPv4 to Cashfree's IP whitelist** (if the account uses one) before the cutover; keep the old one until the rollback window ends.
4. **Copy the data.** The `erpx` and `pentrix` Postgres databases (`pg_dump -Fc`, restore, compare row counts) and all MinIO objects, including generated receipts and credit notes (bucket `erpx-storage`;
   see `docs/operations/offsite-backup.md` and `docs/operations/disaster-recovery-runbook.md`). Run the migration pre-check (section 2) on the new host.
5. **Credentials.** Do not copy `.env` through chat or email. Enter the Live keys on the new host with `cashfreectl.sh keys` (or move the file over a secure channel, then `status`). The keys are not tied to a host, so they need no rotation unless the transfer was insecure.
6. **Bring up the new stack with Cashfree off, then validate.** Containers healthy, restart counts 0, the migration check OK, `https://erp.pentrix.in` served (Caddy gets its certificate once DNS points at the new host, or carry its data volume across to avoid the wait).
7. **Cut over.** Point the A records at the new host. **Switch the old host's Cashfree off and stop its api, worker and Beat** straight away: two hosts with live switches and different database copies would each reconcile the same Cashfree account and record payments only in their own database.
8. **Switch on and validate on the new host.** `switches on`, recreate the three services, `status`, the unsigned webhook probe must answer `401`; wait for one reconciliation tick; then re-enable "Online (Cashfree)" on one internship and repeat the staff payment and refund of section 6.
9. **Rollback.** Before checkouts reopen, rolling back is DNS back to the old host (keep it intact until the new one has passed step 8). After payments have been taken on the new host, going back would lose them: move forward instead (restore a fresh copy to wherever you want to run) or, if you must go back, copy the new database across first.
10. **Afterwards.** Remove the old IP from Cashfree's whitelist and release the old address (an Elastic IP on AWS) once the old host is decommissioned.

## 9. Known limits (unchanged, accepted)

- The adapter has been exercised against the Cashfree sandbox (owner-run, see `docs/CASHFREE_SANDBOX.md`) but never against Live. Step 7 is its first Live run.
- A genuine "user dropped" notification was never observed in the sandbox; ERPX never marks a payment paid from it.
- A student who starts a fresh order while an older Cashfree order is still payable could pay twice (existing overpayment handling applies).
- Payments made while the master switch is off are not recorded automatically.
