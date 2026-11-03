# Cashfree sandbox: configuration, dashboard steps and validation

Merchant: GIR Technologies (OPC) Pvt. Ltd. (account activated). Code: `modules/internship_onboarding/providers/cashfree.py`
(adapter), `payments.py` (orders, webhooks, reconciliation, refunds). Production Cashfree stays off until the owner
authorises it after a passed sandbox run. Never put keys in the repository, a chat, a ticket or a log.

## 1. Contract review (adapter vs Cashfree's published documentation)

Checked against search excerpts of Cashfree's official docs (full pages could not be opened from the development
environment: `www.cashfree.com` is blocked there). Every row still needs the sandbox run in section 5.

| Area | Cashfree documents | ERPX adapter | Result |
|---|---|---|---|
| Hosts | sandbox `https://sandbox.cashfree.com/pg`, production `https://api.cashfree.com/pg` | same | matches |
| Auth headers | `x-client-id`, `x-client-secret`, `x-api-version` | same; secret never logged or returned | matches |
| API version | latest is `2026-01-01` (v6); `2025-01-01` is listed as a previous version and still published. 2026-01-01 adds fields to Create Order / Order Pay and warns that code reading the old response shape can break | pinned to `2025-01-01` (the contract reviewed here); `CASHFREE_API_VERSION` overrides | validate 2025-01-01 in the sandbox first, then 2026-01-01 as a separate step before choosing it for production |
| Create order | `POST /orders`; `order_id` unique, 3-45 chars, letters/digits/`-`/`_`; `customer_details.customer_id` letters/digits/`-`/`_`; `return_url`; returns `payment_session_id` | `ERPXI` + 24 hex chars; customer id = application reference (`ERPX-INT-2026-000001`); amount and currency echoed back are checked | matches |
| Hosted checkout | JS SDK `https://sdk.cashfree.com/js/v3/cashfree.js`, `Cashfree({mode})`, `checkout({paymentSessionId, redirectTarget})`; load from Cashfree's CDN; domain whitelisting | loaded from the CDN on demand; `mode` from the server's environment; `redirectTarget: "_self"`; the return page proves nothing (status is fetched server-side) | matches |
| Payment status | `GET /orders/{order_id}/payments`; statuses SUCCESS, FAILED, USER_DROPPED, PENDING... | SUCCESS confirms (exact amount and currency only); FAILED/USER_DROPPED/CANCELLED/VOID failed; anything else pending | matches |
| Webhook signature | base64(HMAC-SHA256(`x-webhook-timestamp` + raw body, client secret)); use the raw, unparsed body | same, constant-time compare, raw body, 72 h age limit (`CASHFREE_WEBHOOK_MAX_AGE_HOURS`), 401 when invalid so Cashfree retries | matches |
| Webhook delivery | may repeat; may arrive FAILED, PENDING, SUCCESS; update only on SUCCESS; dedupe by `cf_payment_id` | each body stored by hash (exact repeats ignored); one ledger row per `cf_payment_id` (unique index); a late FAILED never overrides SUCCESS | matches |
| Webhook payload | `type`, `data.order.order_id`, `data.payment.cf_payment_id` (string in newer versions), `payment_status`, `payment_amount`; header `x-webhook-version` | parsed the same way; `cf_payment_id` read as text | matches |
| Refunds | `POST /orders/{order_id}/refunds` (`refund_id`, `refund_amount`, `refund_note`); `GET /orders/{order_id}/refunds/{refund_id}`; statuses SUCCESS, PENDING, CANCELLED, ONHOLD, FAILED; within 6 months of payment | same; refund id derived from the ERPX refund row (`RF` + 30 hex), so a retry carries the same id; amount echoed back is checked | matches; the refund webhook (`REFUND_STATUS_WEBHOOK`, `data.refund` with `cf_refund_id`, `refund_status`) matches the parser |
| Auto refunds | `AUTO_REFUND_STATUS_WEBHOOK`: Cashfree's own refunds, without the usual order fields | was refused as unreadable (400, so retried by Cashfree); now acknowledged, matched by `cf_payment_id`, shown on the student's timeline for finance; the ledger is not changed automatically | fixed (tested with a signed notification); payload field names to confirm in the sandbox |
| Order expiry | `order_expiry_time` ISO 8601 | now + `CASHFREE_ORDER_MINUTES` (30, at least 15) in UTC | matches; minimum not confirmed |

What the code guarantees whatever the gateway says (tested with mocked HTTP and real signatures):
- the order amount is what the student owes: the accepted fee snapshot (from the internship's configured fee, INR 2,000 by
  default) plus charges, minus waivers and money already confirmed; never a fixed number;
- nothing is paid, receipted, completed or LMS-granted until a signed notification or a server-side status check reports
  SUCCESS for the order's exact amount and currency; forged, stale, failed, dropped and pending events change nothing;
- one order per obligation while it is active; a payment on an expired order is still recorded (the money arrived).

## 2. What you do in the Cashfree dashboard (Test mode first)

1. Sign in at `merchant.cashfree.com` and switch to **Test mode / Sandbox**.
2. **Developers > API Keys**: generate the sandbox **App ID** and **Secret Key**. Keep them in a password manager; give
   them to ERPX only as environment secrets (section 3), never by chat or email.
3. **Developers > Webhooks**: add the endpoint
   `https://<test host>/api/v1/public/payments/cashfree/webhook`, webhook **version 2025-01-01** (same as
   `CASHFREE_API_VERSION`), events: payment success, payment failed, payment user dropped, refund status (and auto refund status, if offered).
   It must be a public HTTPS address (see section 4 for which host).
4. **Developers > Whitelisting** (domain): add the domain where students open checkout (the test host now;
   `erp.pentrix.in` for production later).
5. Note the sandbox test instruments (cards/UPI IDs) from Cashfree's "test data" page for the run in section 5.

Production, only after the sandbox run and your written authorization: generate production keys in Live mode, add the
webhook `https://erp.pentrix.in/api/v1/public/payments/cashfree/webhook` (version 2025-01-01, same events), whitelist
`erp.pentrix.in`, then set the production variables in section 3.

## 3. ERPX settings

| Variable | Sandbox | Production (later, owner only) |
|---|---|---|
| `CASHFREE_ENABLED` | `true` | `true` |
| `CASHFREE_ENV` | `sandbox` | `production` |
| `CASHFREE_ALLOW_PRODUCTION` | unset (false) | `true` |
| `CASHFREE_APP_ID` / `CASHFREE_SECRET_KEY` | sandbox keys (secret) | production keys (secret) |
| `CASHFREE_API_VERSION` | `2025-01-01` (default) | same as tested |
| `CASHFREE_ORDER_MINUTES` | `30` (default) | `30` |
| `CASHFREE_WEBHOOK_MAX_AGE_HOURS` | `72` (default) | `72` |
| `FRONTEND_URL` | the test host (`https://...`); the checkout return URL is built from it | `https://erp.pentrix.in` |

The production environment keeps `CASHFREE_ENABLED` unset until you authorise it. Each internship then offers
"Online (Cashfree)" only when finance enables it in its Settings (it stays hidden while the server has Cashfree off).

Network: the server calls `sandbox.cashfree.com` (later `api.cashfree.com`); students' browsers load
`sdk.cashfree.com` and open Cashfree's checkout pages. If a Content-Security-Policy is added to the web server, allow
those. For a Claude Code cloud session: allow `sandbox.cashfree.com` and `www.cashfree.com` under the environment's
Network access, and add `CASHFREE_APP_ID`, `CASHFREE_SECRET_KEY` (sandbox keys) as environment secrets.

## 4. Readiness (updated 2026-11-03)

| Item | Status |
|---|---|
| Adapter, webhook, reconciliation and refund code | reviewed against the current docs; mocked tests with real signatures pass; fixes: auto refunds, standalone bootstrap seed |
| Sandbox keys, public HTTPS webhook endpoint, isolated staging | **available** on the owner's Mac (`ops/staging-cashfree/`, Cloudflare quick tunnel, Test-mode keys only) |
| Sandbox acceptance | scenarios 1-7a passed on the Mac as reported (4a); untested items are listed in 4a-i |
| Cloud session access to Cashfree | still blocked (proxy); not needed any more, the sandbox run happens on the Mac |
| Production | untouched; Cashfree stays off there (`CASHFREE_ENABLED` unset) |

## 4a. Sandbox acceptance record

Sources: **Mac** = observed by the owner on the Mac staging stack (2026-11-02/03), as reported to the author of this
document; **Test** = automated test in this repository (mocked Cashfree HTTP, real HMAC signatures, real database).
No result below is claimed from a source it does not list. The Mac evidence snapshots (`ops/staging-cashfree/evidence/`,
for example `20261103T072028Z`) are git-ignored and stay on the owner's Mac; they were **not** available to the author,
so the figures taken from them are the owner's report, not independently reviewed. Code statements were checked in
this repository.

| # | Scenario | Result | Source |
|---|---|---|---|
| 1 | ₹2,000 order for the configured fee, hosted checkout, sandbox payment (twice) | passed | Mac |
| 2 | Success webhook -> HTTP 200 -> payment confirmed once -> receipt PDF + email | passed | Mac; Test |
| 3 | Same success webhook delivered again -> HTTP 200, still one payment and one receipt | passed | Mac |
| 3a | Replay adds no second receipt **email**, payment row or accounting entry (exact repeat, re-wrapped copy, status check) | passed: `./staging.sh evidence` on the Mac showed 0 duplicate payments, 0 duplicate documents, 0 missing documents, 0 accounting journal entries, and each receipt / credit-note email once (Mailpit) | Test; Mac |
| 4 | ₹1 sandbox refund -> refund webhook -> credit note `RCPT-CN-2026-000001` emailed (Mailpit) | passed | Mac |
| 4a | ₹1 refund counted once: ledger = payment 2,000 + refund 1 + waiver 1 (`refund_adjustment`); student owes 1,999 and has paid 1,999 net; balance 0; dashboard received 1,999 | passed: the waiver lowers what is owed, the refund lowers what was paid, so the ₹1 is not counted twice; Mac evidence: 0 refund-adjustment mismatches | Test; Mac |
| 4b | Refund idempotency: one open refund per payment (second request 409); one gateway call with an id derived from the refund row; refund-webhook replays (exact and re-wrapped) change nothing; one credit note, emailed once | passed | Test |
| 5 | Failed payment (`testfailure@gocash`) -> no receipt, student can retry with a new order | passed: the student stayed unpaid, no receipt was issued, and a successful retry created a new order | Mac; Test |
| 6 | Checkout closed / user dropped -> no receipt, stays unpaid, retry possible | passed **on manual checks only**: the student stayed unpaid, got no receipt and could retry; no evidence figures or timeline entry were reviewed for this case, and it is not known whether Cashfree sent a "user dropped" notification | Mac (manual); Test |
| 7 | Lost webhook (gateway returned HTTP 503 to Cashfree while the sandbox payment succeeded) -> ERPX confirms the payment on its own, exactly once | passed: ERPX confirmed the payment and issued receipt `RCPT-2026-000004` **without the manual "I have paid: check status" button being used**; the receipt appeared exactly once in Mailpit. Most likely path: the portal's automatic status check on the return page; **likely, not proven** (see 4a-ii) | Mac; Test |
| 7a | Webhooks delivered after the endpoint was restored: Cashfree delivered two payment-success notifications for payment `1471038895188844032`, both acknowledged HTTP 200 | passed: nothing was added (per the code, a success for a payment already confirmed returns 200 and adds nothing to the ledger, and an identical body is answered "duplicate"); owner's evidence: 0 duplicate payments, 0 duplicate documents, 0 missing documents, 0 refund-adjustment mismatches, 0 unexpected accounting entries. Which of the two answers each delivery received comes from the webhook table in the snapshot, which was not reviewed | Mac; Test |
| 7b | Manual "I have paid: check status" button, used on its own for a lost webhook | **not tested** in the sandbox. Two attempts (rows 7 and 7c) ended in the automatic return-page check before the button could be pressed. An isolated procedure now exists (`./staging.sh gate on`, section 4a-iii); the server side (page load never confirms, the explicit check confirms once, repeats and late webhooks change nothing) is covered by an automated test | Test |
| 7c | Second lost-webhook run: Student D (`ERPX-INT-2026-000007`), ₹2,000 sandbox payment with the webhook blocked (HTTP 503). Cashfree redirected the browser to `/internship-onboarding?order=...`, and ERPX confirmed the payment automatically; receipt `RCPT-2026-000005` issued once, its email appears once in Mailpit | passed as an **automatic-recovery** test, **not** a manual-button pass: the button could not be tested because the return page confirmed first. After the nginx change was reverted `./staging.sh verify` passed; evidence `20261103T075929Z`: zero problems across all five integrity checks | Mac (owner-reported; snapshot not reviewed) |
| 8 | First checkout stayed on Cashfree's return page, second returned | not reproduced in code; see 4b below | Mac |

### 4a-i. Completed and untested, at a glance

**Completed in the sandbox on the Mac:** successful payments (twice); success webhook and replay; receipt and email once;
the ₹1 refund and its credit note; failed payment and retry; checkout cancelled (manual checks); automatic recovery of a
payment whose webhook was refused (twice: `RCPT-2026-000004` and, for Student D, `RCPT-2026-000005`), and the later
duplicate webhooks. Owner-reported evidence: 0 duplicate payments, 0 duplicate documents, 0 missing documents, 0
refund-adjustment mismatches, 0 unexpected accounting entries; each receipt once in Mailpit.

**Not tested in the sandbox (do not read these as passed):**
- the manual "I have paid: check status" button as the thing that recovers a lost webhook (row 7b; the isolated
  procedure in 4a-iii has not been run yet);
- the mechanism that recovered `RCPT-2026-000004` is a likely explanation, not a proven one (4a-ii): the return page's
  automatic status check (the second run, row 7c, behaved the same way); the 15-minute reconciliation task has **not** been seen working against the real sandbox;
- Cashfree actually sending a "payment user dropped" notification for a closed checkout (row 6 is a manual observation);
- an auto-refund notification (`AUTO_REFUND_STATUS_WEBHOOK`): tests only, with a mocked body;
- API version `2026-01-01` (production stays on the pinned `2025-01-01`);
- the stuck return page (row 8) is still unexplained;
- anything on production: no production keys, webhook, domain whitelist or live payment has been used (4c).

### 4a-ii. How the lost-webhook payment was recovered (timeline + code review: a likely explanation, not proof)

While the gateway answered 503, Cashfree's notifications never reached ERPX (ERPX's webhook handler only answers 503 when
Cashfree is not configured, so the 503 came from the staging gateway). In the code, an order can only be confirmed by a
webhook, or by `refresh_order` -> `apply_gateway_payment`, which records a payment once per Cashfree payment id and issues
the receipt. `refresh_order` has exactly two callers:

1. **The student endpoint** `POST /payments/refresh`, called by the portal automatically when the browser comes back to
   `/internship-onboarding?order=...` (`onboarding-portal-page.tsx`) and by the "I have paid: check status" button.
2. **The reconciliation task** `internship_onboarding.reconcile_payments`, every 15 minutes, only for active Cashfree
   orders **older than 10 minutes** that were not checked in the last 10 minutes.

Administrator timeline for `RCPT-2026-000004` (reported by the owner, 3 November 2026, IST; minute resolution): checkout
started 12:32, payment confirmed 12:33, document issued 12:33, payment completed 12:33; Cashfree's webhook attempts at
12:33 and 12:35 both received 503; the student returned from Cashfree and ERPX showed Paid without the button being used.

Reasoning from that and the code:
- **Not the webhook:** both attempts were refused with 503 (the first in the same minute as the confirmation).
- **Not the reconciliation task:** the order was about one minute old at 12:33, and the task skips orders younger than 10
  minutes. The "checkout started" entry is only written when a new order is created (reusing an unpaid order returns
  before that line), so the order was not an older one that was reused.
- **That leaves the student endpoint,** and since the button was not clicked, the return page's automatic call.

This is the most likely explanation, **not a proven mechanism**: the timeline has minute resolution, the page-load call and
the button call the same endpoint and are not distinguished in the record (both give the source "status check"), "the
button was not clicked" is the owner's observation, and nothing logs which request confirmed the payment. The result that
matters holds either way: the payment was confirmed once, with one receipt and one email, while the webhook was refused,
and the two late webhooks changed nothing.

A second run (row 7c, Student D) behaved the same way: with the webhook blocked, the redirect to
`/internship-onboarding?order=...` was followed by automatic confirmation. That is consistent with this explanation but is
the owner's observation, not a logged proof. The button is tested separately with the gate in 4a-iii (closing the Cashfree
tab is not reliable: the redirect happens on its own).

### 4a-iii. Testing the button on its own: the staging test gate

Why a procedure is needed: Cashfree's `return_url` is fixed when the order is created and points at
`/internship-onboarding?order=...`. When the browser lands there, the web app calls `POST /payments/refresh` by itself, so
the payment is confirmed before anyone can press the button (rows 7 and 7c). The webhook can be blocked; the return
redirect cannot be avoided from the browser.

`./staging.sh gate on` isolates the button by changing only the **staging gateway** (and one staging container):
1. Cashfree's webhook endpoint answers 503 (the webhook is "lost");
2. the return page (`/internship-onboarding?order=...`) is answered by the gateway with a static "test gate is on" page, so
   the web app never loads there and never sends its automatic check;
3. `celery_beat` is stopped, so the 15-minute reconciliation cannot confirm the payment either.
The page without `?order=` and the API (including `POST /payments/refresh`, which the button calls) stay open. `./staging.sh
gate off` undoes all three. `gate on` checks the new gateway configuration with `nginx -t` before reloading and rolls back
if it is rejected; `up` and `refresh-app` refuse to run while the gate is on (they would restart the reconciliation).

What it is not: no application code, web app, payment verification, signature check or rate limit is changed, and nothing
in it can be reached on production: the gate files are staging-only (`ops/staging-cashfree/gate-templates/`, mounted by the
staging compose file), and the confirmation still requires the student's token and a server-to-server answer from Cashfree
for the exact amount. The refresh endpoint is not bypassed; the *other* triggers are removed so the test shows what the button does.

Procedure (Mac): `./staging.sh gate on`; make a synthetic student ready to pay; pay with `testsuccess@gocash`; Cashfree
shows its success page and the browser lands on the gate page; ERPX must still show the student as unpaid; open the
student's onboarding link without `?order=`, press "I have paid: check status"; then `./staging.sh gate status` and
`./staging.sh evidence`; finally `./staging.sh gate off`.

Pass criteria: (a) before the button, the student is unpaid with no receipt; (b) after it, Paid, one payment, one receipt
`RCPT-...` once in Mailpit, and the timeline's "payment confirmed" source is "status check"; (c) `gate status` lists
exactly one `POST .../payments/refresh`, made after the gate went on, so it was the button (with the return page blocked
nothing else calls it); (d) the webhook count is 503 only and the five evidence checks are 0; (e) after `gate off`, when Cashfree retries (or the notification is resent from the dashboard), the
notification is acknowledged without a second payment or receipt. Record the result as row 7b.

Tests: `tests/unit/test_staging_gateway.py` runs the real gateway configuration and gate templates in a real nginx with stub
upstreams (gate off: unchanged; gate on: webhook 503 and never reaches the API, return page never reaches the web app,
the page without `?order=`, the refresh endpoint, other API calls and other pages stay open; gate off again restores both);
`ops/staging-cashfree/tests/gate_test.sh` covers the script (install, validate, rollback, beat stopped and restarted, no
network changes); `tests/api/test_internship_onboarding_cashfree.py::test_a_lost_webhook_is_recovered_only_by_the_students_explicit_status_check`
covers the server side. None of these is a sandbox run.

### 4b. The stuck return page (first checkout)

ERPX never relies on the return page for money: payments are confirmed only by a signed webhook or a server-side status
check, so the first payment was recorded correctly either way. The return address is fixed when the order is created
(`FRONTEND_URL` + `/internship-onboarding?order=<id>`), and an unpaid order with the same amount is reused for up to 30
minutes. On the Mac, `FRONTEND_URL` is the quick-tunnel address the API was started with; if the tunnel was restarted
(new address) or the order was created before `./staging.sh up` picked up the address, Cashfree redirects to an
address that no longer exists and the browser stays on Cashfree's page. To confirm: compare the first order's
`created_at` (`./staging.sh evidence`, "payment orders") with when the tunnel address last changed, and look at that
order's return URL in the Cashfree dashboard (Test mode, order details). In production `FRONTEND_URL` is fixed
(`https://erp.pentrix.in`), so this cause cannot occur there; if it is something else (a Cashfree-side delay), it does
not affect what ERPX records. No code change was made for it.

### 4c. Before a controlled production rollout

1. Sandbox scenarios 5, 6 and 7 are done on the Mac (4a, evidence checks at 0, one email per receipt). Still open from
   4a-i, owner's call on whether they are needed before a controlled start: the button on its own (7b), the 15-minute
   reconciliation task against the real sandbox (the lost-webhook recovery is most likely the return page, 4a-ii), and a
   real "user dropped" notification (row 6).
2. Review and merge PR #163 (owner).
3. Production prerequisites (owner): production App ID / Secret Key as server secrets only; webhook
   `https://erp.pentrix.in/api/v1/public/payments/cashfree/webhook` (version 2025-01-01, payment + refund events);
   `erp.pentrix.in` whitelisted; `CASHFREE_ENABLED=true`, `CASHFREE_ENV=production`, `CASHFREE_ALLOW_PRODUCTION=true`
   set only with written authorization; the production MinIO image issue (official `minio/minio` can no longer be pulled)
   resolved before any rebuild of that host.
4. Controlled start (owner's decision): one internship, "Online (Cashfree)" enabled by finance, one real low-value payment by a staff member
   and its refund, then open to students.

## 5. Where the sandbox run happens

An isolated staging stack, never production: `ops/staging-cashfree/` (self-contained `compose.yml`, project
`erpx-cf-staging`: own Postgres, Redis and MinIO, no published ports except the gateway and Mailpit viewer on
127.0.0.1, Mailpit for all email, synthetic data only, sandbox keys only, a preflight that refuses production keys,
hosts, unsafe ports and leaked secrets; `./staging.sh` drives it). Options:
- **A. The owner's Mac (Apple Silicon) with Docker Desktop + a Cloudflare quick tunnel** (free, no AWS, no DNS
  change): chosen for the validation run; step-by-step in `ops/staging-cashfree/README.md`.
- **B. A separate small EC2 instance** (roughly US$15-20 per month while running) with a staging host name: needs the
  owner's approval for paid resources and a DNS record.

## 6. Validation run

The step-by-step run (INR 2,000 payment with `testsuccess@gocash`, failure with `testfailure@gocash`, cancellation,
duplicate webhook, lost webhook recovered by the status check, refund with credit note, optional 2026-01-01 pass) is in
`ops/staging-cashfree/README.md`. Record each result in `docs/INTERN_ONBOARDING_PROGRESS.md`. Mocked tests are not a
substitute: sandbox acceptance is claimed only after that run. Then the owner decides on production keys and
`CASHFREE_ALLOW_PRODUCTION`.
