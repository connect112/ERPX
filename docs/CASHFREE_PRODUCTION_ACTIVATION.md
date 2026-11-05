# Cashfree live payments: activation guide for the AWS production host

Status of this document: **preparation only**. Nothing here has been run on the production host. Live payments stay off until the owner
authorises each step below. Companion records: `docs/CASHFREE_SANDBOX.md` (what the sandbox acceptance covered and its limits) and
`docs/CASHFREE_REVIEW_HANDOFF.md` (security review, release blockers, rollback reasoning).

Never put a key in git, a chat, a ticket, a shell command line, SSM Run Command parameters, or a log. Keys live only in
`/opt/erpx/.env` (owner `root`, mode `600`). `ops/cashfree-production/cashfreectl.sh` is the one way this guide stores them.

## 1. What the repository now provides

| Piece | What it does |
|---|---|
| `docker-compose.prod.yml` (`x-backend-env`) | Passes the eight `CASHFREE_*` settings to `api`, `celery_worker` and `celery_beat` (the only services that run the app; they share that block). Every name has a safe default, so merging this changes nothing: Cashfree stays **off**, the sandbox is the default environment, and live mode needs its own switch. No other service (MinIO, the four web portals) receives them. |
| `ops/cashfree-production/cashfreectl.sh` | `status` / `keys` / `switches on` / `switches off`. Reads keys from a hidden prompt, never prints a value, edits only `CASHFREE_*` lines, replaces the file in one step, forces mode 600, and asks for a typed confirmation before the live switches. |
| `tests/unit/test_prod_compose_cashfree.py` | Fails if a setting is added to the app but not to the Compose file, if Cashfree could default to ON, if a value is hard-coded, or if a non-app service receives payment settings. |

The three switches that must all be on for a live payment (a sandbox setup can never take real money by mistake):

| Name | Live value | Default |
|---|---|---|
| `CASHFREE_ENABLED` | `true` | `false` |
| `CASHFREE_ENV` | `production` | `sandbox` |
| `CASHFREE_ALLOW_PRODUCTION` | `true` | `false` |

Plus `CASHFREE_APP_ID` and `CASHFREE_SECRET_KEY` (the **Live** pair, not the Test pair). `CASHFREE_API_VERSION` stays `2025-01-01` (the version
the adapter was validated on, and it must equal the webhook version); `CASHFREE_ORDER_MINUTES=30` and `CASHFREE_WEBHOOK_MAX_AGE_HOURS=72` stay at their defaults.

Checked on this change with fake values: the rendered Compose differs from master only by those eight names on those three services;
with nothing set they render as off; the app's settings parse them; production mode is refused unless `ALLOW_PRODUCTION` is true, and
refused with empty keys.

## 2. Before anything touches production (all owner)

- [ ] This change reviewed and merged by the owner.
- [ ] A fresh, restorable backup of the database and `erpx_minio_data` (`docs/operations/offsite-backup.md`); last night's off-server run succeeded.
- [ ] Disk has room: `df -h /` shows at least 3 GB free. (Activation needs no image build, but containers are recreated and logs grow.)
- [ ] A named rollback owner and someone on call for the first day.
- [ ] Server egress IP known and stable (section 5). **If the instance is ever stopped/started or resized, a public IP that is not an Elastic IP changes.**
- [ ] The production SMTP relay works: receipts and refund credit notes are emailed. Send one test through an existing flow first.
- [ ] Finance has the internship's fee, payment accounts and receipt details configured (Finance screens), and the student phone numbers are 10-digit mobiles (checkout refuses without one).
- [ ] The owner's written go-ahead for `CASHFREE_ALLOW_PRODUCTION=true`.

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

**Step 2: store the keys** (still off). Open a shell on the host that does not record what you type: an SSH session, or the AWS console's Session Manager
only if session logging to S3/CloudWatch is off. **Do not use Run Command**: its command text is kept in history.
```bash
sudo /opt/erpx/ops/cashfree-production/cashfreectl.sh keys     # typing is hidden; nothing is printed
sudo /opt/erpx/ops/cashfree-production/cashfreectl.sh status   # keys show as <set, hidden>; mode must be 600, owner root
```
The values must be the **Live** App ID and Secret Key. Characters other than letters, digits, `_`, `-` and `.` are refused (Compose would alter them).

**Step 3: the dashboard, before switching on** (section 4): domain whitelist, and the IP whitelist if the account has it. Do **not** register the webhook yet.

**Step 4: switch on, and confirm the endpoint is live and rejecting.**
```bash
sudo /opt/erpx/ops/cashfree-production/cashfreectl.sh switches on        # asks you to type I AUTHORIZE LIVE PAYMENTS
cd /opt/erpx && docker compose -f docker-compose.prod.yml up -d --no-deps api celery_worker celery_beat
docker exec erpx_api python -c "from app.core.config import settings as s; print('cashfree enabled:', s.CASHFREE_ENABLED, 'env:', s.CASHFREE_ENV, 'production allowed:', s.CASHFREE_ALLOW_PRODUCTION, 'keys set:', bool(s.CASHFREE_APP_ID), bool(s.CASHFREE_SECRET_KEY))"
curl -s -o /dev/null -w "webhook: HTTP %{http_code}\n" -X POST https://erp.pentrix.in/api/v1/public/payments/cashfree/webhook -d '{}'
```
Expected: `enabled: True env: production production allowed: True keys set: True True`, and the unsigned webhook now answers **HTTP 401** (live, and rejecting forgeries).
Restart counts still 0. Within 15 minutes the worker log shows the scheduled reconciliation running with nothing to do
(`docker logs --since 20m erpx_celery_worker | grep -i reconcile`). If the provider refuses to build, the log says why without printing a key.

**Step 5: register the webhook** (section 4). Registering after step 4 means Cashfree never meets a 503.

**Step 6: offer it to one internship only.** In the app, open that internship's onboarding settings, find the payment methods, and enable "Online (Cashfree)" (finance does this). (The app refuses this while the server has Cashfree off, which is why it comes after step 4.)

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

**IP whitelist** (same area, if the account has API IP whitelisting turned on, which I could not verify from the repository): add the host's **public egress
IPv4**. Find it on the host with `curl -s https://checkip.amazonaws.com`, and confirm it equals the A record of `erp.pentrix.in`. It applies to calls ERPX makes
(create order, status check, refund), not to webhooks Cashfree sends. Without it those calls fail with "the payment gateway refused the request (4xx)" while
webhooks still arrive. Attach an **Elastic IP** first so the address survives a stop/start or a resize (same hourly price as the current public IPv4).

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
2. Within a minute: the order shows paid; in the Cashfree dashboard, Developers, Webhooks, Logs shows the success event delivered with `200`; exactly one receipt and one email.
3. Read-only evidence (selects only, no secrets): `docker exec -i shared_postgres psql -U erpx -d erpx < /opt/erpx/ops/staging-cashfree/evidence.sql`. Every line under `CHECKS` must be `0`.
4. Refund that payment from the finance screen. Confirm the refund webhook arrives, the refund shows confirmed (Cashfree may hold it as PENDING or ONHOLD first), one credit note is issued, and the net figures are right.
5. Watch two reconciliation ticks (30 minutes): nothing unexpected is "confirmed" or "mismatched".
6. Only then widen (step 8).

**Abort at once, and stop new checkouts (rollback step 1), if any of these happens:** a duplicate payment, receipt or email; a `payment_mismatch`; a webhook with a valid
signature that is not recorded; any of the three Celery/API containers restarting; a student charged but shown unpaid for longer than the reconciliation window (about 90 minutes).

## 7. Rollback (least disruptive first)

1. **Stop new checkouts, keep the plumbing.** Remove "Online (Cashfree)" from the internship's payment methods. Leave `CASHFREE_ENABLED=true` and the webhook registered so payments already in flight are still recorded.
2. **Wait** until no Cashfree order is open (30-minute order life plus a 60-minute grace) and nothing is pending (including refunds).
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

## 8. Known limits (unchanged, accepted)

- The adapter has been exercised against the Cashfree sandbox (owner-run, see `docs/CASHFREE_SANDBOX.md`) but never against Live. Step 7 is its first Live run.
- A genuine "user dropped" notification was never observed in the sandbox; ERPX never marks a payment paid from it.
- A student who starts a fresh order while an older Cashfree order is still payable could pay twice (existing overpayment handling applies).
- Payments made while the master switch is off are not recorded automatically.
