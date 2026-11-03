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
| Sandbox acceptance | scenarios 1-7c passed on the Mac as reported, the manual status-check button (7b) with qualifications (4a, 4a-iii); untested items are listed in 4a-i |
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
| 7b | Manual "I have paid: check status" button, used on its own for a lost webhook (isolated with `./staging.sh gate on`) | **passed, with qualifications.** Student E (`ERPX-INT-2026-000008`), ₹2,000, Cashfree payment `1471061513720561664`: with the gate on (from 2026-11-03T08:25:33Z) the webhook was refused (four 503s in the cumulative gate log, not attributed per student), one Cashfree return-page request was blocked, Celery Beat was stopped, and the payment changed to Paid after the student pressed "I have paid: check status" (owner's observation). Receipt `RCPT-2026-000006` issued once; its email appears once in Mailpit. Gateway log: two `POST /payments/refresh` answered 200, at 08:29:00 and 08:33:55 UTC; the second aligns with the click, the **first is not attributed to Student E**. Owner-reported evidence `20261103T083944Z`: 0 duplicate payments, 0 duplicate documents, 0 missing documents, 0 refund-adjustment mismatches, 0 unexpected accounting entries. Restored: `gate off` completed, `gate status` OFF, Celery Beat running, `verify` passed (unsigned webhook refused with 401). Not reported: the timeline's "source" for the confirmation, and a retried webhook after `gate off`. See 4a-iii for the criteria | Mac (owner-reported; snapshot and gate log not reviewed); Test |
| 7c | Second lost-webhook run: Student D (`ERPX-INT-2026-000007`), ₹2,000 sandbox payment with the webhook blocked (HTTP 503). Cashfree redirected the browser to `/internship-onboarding?order=...`, and ERPX confirmed the payment automatically; receipt `RCPT-2026-000005` issued once, its email appears once in Mailpit | passed as an **automatic-recovery** test, **not** a manual-button pass: the button could not be tested because the return page confirmed first. After the nginx change was reverted `./staging.sh verify` passed; evidence `20261103T075929Z`: zero problems across all five integrity checks | Mac (owner-reported; snapshot not reviewed) |
| 8 | First checkout stayed on Cashfree's return page, second returned | not reproduced in code; see 4b below | Mac |
| 9 | **Automatic reconciliation by the scheduled task** when the webhook, the return-page check and every student status check are unavailable and nobody presses anything | **NOT YET RUN: do not read this as passed.** Tooling and a procedure now exist (`./staging.sh recon`, section 4a-iv); the task body, its Beat schedule entry and the report SQL are covered by automated tests only | Test |

### 4a-i. Completed and untested, at a glance

**Completed in the sandbox on the Mac:** successful payments (twice); success webhook and replay; receipt and email once;
the ₹1 refund and its credit note; failed payment and retry; checkout cancelled (manual checks); automatic recovery of a
payment whose webhook was refused (twice: `RCPT-2026-000004` and, for Student D, `RCPT-2026-000005`), and the later
duplicate webhooks; the manual status-check button on its own, with the return page, webhook and reconciliation
isolated (Student E, `RCPT-2026-000006`, row 7b, with the qualifications in 4a-iii). Owner-reported evidence: 0 duplicate payments, 0 duplicate documents, 0 missing documents, 0
refund-adjustment mismatches, 0 unexpected accounting entries; each receipt once in Mailpit.

**Not tested in the sandbox (do not read these as passed):**
- for the button run (row 7b): which of the two `POST /payments/refresh` calls (08:29:00 and 08:33:55 UTC) confirmed
  Student E's payment is **not proven** (the second aligns with the click; the first is unattributed); the timeline
  "source" for that confirmation and a retried webhook after `gate off` were not reported;
- the mechanism that recovered `RCPT-2026-000004` is a likely explanation, not a proven one (4a-ii): the return page's
  automatic status check (the second run, row 7c, behaved the same way); the 15-minute reconciliation task has **not** been seen working against the real sandbox (row 9: the test mode and report exist, 4a-iv; not run yet);
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
`RCPT-...` once in Mailpit, and the timeline's "payment confirmed" source is "status check"; (c) note the clock time of
the click; `gate status` must list a `POST .../payments/refresh` at that time. The gateway log has no student identity and
the page is also used by other testers, so other entries are not attributed unless their time matches (Student E's run
showed two entries; see the result below), and with the return page blocked nothing automatic calls it; (d) the webhook count is 503 only and the five evidence checks are 0; (e) after `gate off`, when Cashfree retries (or the notification is resent from the dashboard), the
notification is acknowledged without a second payment or receipt. Record the result as row 7b.

**Result of the first run (Student E, owner-reported 2026-11-03; the evidence snapshot `20261103T083944Z` and the gate log
are git-ignored on the Mac and were not available to the author):**

| Criterion | Result |
|---|---|
| (a) unpaid before the button | reported: the payment changed to Paid after the click. No separate check of "no receipt before the click" was reported |
| (b) Paid, one payment, one receipt, one email | reported: `RCPT-2026-000006` once in Mailpit; evidence checks 0 (duplicates, missing documents, refund mismatches, accounting entries). The timeline "source" was **not reported** |
| (c) a status check at the time of the click | met with a qualification: two `POST /payments/refresh` (200) at 08:29:00 and 08:33:55 UTC. The second aligns with the click. The first is **not attributed** to Student E: it may be another tester's, an earlier press, or something else, and the log does not say which |
| (d) webhook refused, five checks 0 | reported: four 503s (cumulative since the gate went on, so not all necessarily Student E's), one return-page request blocked, Celery Beat stopped; five checks 0 |
| (e) retried webhook after `gate off` | **not reported**, so not claimed |
| Restoration | reported: `gate off` completed, `gate status` OFF, Celery Beat running, `verify` passed including the unsigned-webhook check (HTTP 401) |

Reading it: with the webhook refused, the return page blocked and the reconciliation stopped, the only path left to confirm
the payment was an explicit status check. The payment was unpaid until the student pressed the button, which fits the
second call. The result is therefore recorded as a pass with qualifications, not as a fully attributed single call. Two
things would settle the attribution if the owner wants it: the timeline's "payment confirmed" time for `RCPT-2026-000006`
(08:33:55 UTC is 14:03 IST; 08:29:00 UTC is 13:59 IST, minute resolution) and its "source".

Tests: `tests/unit/test_staging_gateway.py` runs the real gateway configuration and gate templates in a real nginx with stub
upstreams (gate off: unchanged; gate on: webhook 503 and never reaches the API, return page never reaches the web app,
the page without `?order=`, the refresh endpoint, other API calls and other pages stay open; gate off again restores both);
`ops/staging-cashfree/tests/gate_test.sh` covers the script (install, validate, rollback, beat stopped and restarted, no
network changes); `tests/api/test_internship_onboarding_cashfree.py::test_a_lost_webhook_is_recovered_only_by_the_students_explicit_status_check`
covers the server side. None of these is a sandbox run.

### 4a-iv. Automatic reconciliation test (row 9): `./staging.sh recon`

**Does the existing implementation support the test? Yes; no architectural blocker was found.** Checked in the code:
- `internship_onboarding.reconcile_payments` is on the Beat schedule every 15 minutes (`crontab(minute="*/15")`, UTC), is registered
  by the worker (`modules.internship_onboarding` is in the Celery include list, no queue routing), and the staging compose file
  runs Beat and a worker with `--loglevel=info` and `CASHFREE_ENABLED=true`.
- `_reconcile()` takes the open Cashfree orders (`status=active`) that are **older than 10 minutes** and were not checked in the
  last 10 minutes, asks Cashfree for each order's payments (`refresh_order`), and confirms a successful payment of the exact
  amount through the same function the webhook uses. It returns `{'checked': n, 'confirmed': m}`, which Celery logs when the task
  succeeds. Only two things call `refresh_order`: this task and the student's `POST /payments/refresh` (button and return page).
  So with the webhook refused and that endpoint refused, the scheduled task is the only way left to confirm.
- A paid order that nothing else confirms therefore waits **10 to about 25 minutes** (10 minutes of age, then the next :00, :15,
  :30 or :45 UTC tick). That is the real behaviour under test; the test does not shorten it or call the task by hand.

**Limits to know about (they shape the evidence, they are not blockers):**
- The timeline entry says "status check" whether the student endpoint or the scheduled task made it, so the timeline alone cannot
  prove who did it. The proof is the combination: the student endpoint was refused at the gateway, the webhook was refused, the
  confirmation came at least 10 minutes after checkout, and the worker log shows the scheduled task finishing with
  `'confirmed': 1` within seconds of the confirmation, after Beat's "Sending due task" line.
- The application does not log its own request to Cashfree. The worker's HTTP client may log it (the report shows such lines if
  they exist, as corroboration only); the confirmation itself can only come from Cashfree's answer for the exact amount.
- Beat and worker logs live in the containers: do not recreate them during the test (`up` and `refresh-app` refuse while the test
  mode is on). A direct call to the API inside Docker (not through the gateway) would not be seen; nothing in the procedure makes one.

**The isolation (staging gateway only; no application code, no change to the task, its schedule or the workers):**
`./staging.sh recon on` makes Cashfree's webhook endpoint answer 503, answers the checkout return page
(`/internship-onboarding?order=...`) at the gateway so the web app never loads there, and makes the student's status-check
endpoint answer 503 (so even an accidental button press cannot confirm; such attempts are counted and reported). Checkout, the
student page without `?order=` and the rest of the API stay open. `celery_beat` and `celery_worker` keep running and are never
stopped, restarted or modified (`recon on` refuses if either is not running). It excludes `gate on` (which stops Beat) and the
other way round.

**Commands (Mac, from `ops/staging-cashfree`):**
- `./staging.sh recon check`: read-only readiness (Beat and worker up, the task registered, Beat has been sending it, when the worker last
  ran it). Run it first. See "Readiness check" below.
- `./staging.sh recon run ERPX-INT-2026-0000NN 45`: turns the mode on, waits up to 45 minutes for that student's order to become
  paid in ERPX (checks every 30 seconds), prints the evidence report, and **always rolls back** (also on timeout, failure, Ctrl-C,
  SIGTERM or a closed terminal). Use `caffeinate -i` so the Mac does not sleep: a sleeping Mac pauses Beat as well.
- Manual alternative: `recon on`, then `recon status` while waiting, then `recon report ERPX-INT-2026-0000NN`, then `recon off`.
- `./staging.sh recon off` is the rollback and is safe to run any time, any number of times: it removes every gate file, reloads the
  gateway (restarting only the gateway if the reload fails), and starts Beat and the worker if they are not running. After it,
  `./staging.sh gate status` shows "gate: off" and `./staging.sh verify` should pass.

**Readiness check (corrected after its first Mac run).** The first version of `recon check` printed "the worker does not list the
reconciliation task" and "Beat has not sent it in the last 20 minutes" although the staging logs show Beat dispatching the task at
09:00 and 09:15 UTC and the worker running it at 09:15 (`{'checked': 0, 'confirmed': 0}`). That was a fault of the checker, not of the
reconciliation, which was working. The exact cause could not be determined from here; the checker had several weaknesses, all fixed:
it ran `celery inspect` with the default 1-second timeout and without naming the node (a reply on Docker Desktop can take longer) and
threw its error output away; it tested both answers with `producer | grep -q` under `pipefail`, which reports "not found" when the
producer is killed by SIGPIPE after grep has already matched (reproduced with a reply larger than the pipe buffer; the real reply is
small, about 1.5 KB, so this is less likely for the registration check); and it looked only at the last 20 minutes of Beat's log for an
exact phrase. The check now asks one node with `-t 20 -d celery@<host>`, shows what `inspect` said, accepts the worker's own log
(its task list, or a run that succeeded) when `inspect` does not answer, finds Beat's newest "Sending due task ... reconcile" line in
its whole log and judges it by its timestamp (Docker's, or Celery's own), says when the worker last ran the task and with what
result, and uses no pipe into `grep -q`. It is read-only and starts, stops or restarts nothing. Its tests use log lines in the formats
of Celery 5.4 and `docker compose logs --timestamps`; they are representative, not copied from the Mac. This changed no reconciliation
logic, and row 9 is still **not run**.

**Procedure:** `recon check`; then in one terminal `caffeinate -i ./staging.sh recon run <application ref> 45`, and in the
browser: make a synthetic student ready to pay, press Pay, pay with `testsuccess@gocash`, let the Cashfree page finish, and **do
not press any status button**. Wait. The report appears when ERPX shows the order as paid (or after 45 minutes).

**Pass criteria (all must hold; the report prints each as PASS or FAIL):**
1. The mode was on before checkout started; no Cashfree notification was accepted by the gateway and none reached ERPX; no student
   status check reached ERPX (blocked attempts are listed, not counted against the test).
2. Beat sent the task; the worker ran it and it confirmed at least one payment; ERPX recorded the confirmation within 120 seconds
   of the end of that run; the confirmation came at least 10 minutes after checkout; its source is "status check" and the
   order's `last_checked_at` matches it.
3. The order is paid with exactly one confirmed payment, one receipt and one `payment_confirmed` event; exactly one receipt email
   for that receipt number in Mailpit; the five integrity checks are 0 (duplicate payments, duplicate documents, confirmed payments
   without a document, refund-adjustment mismatches, accounting journal entries).
The report also saves filtered gateway, Beat and worker lines and the database facts in `evidence/recon-<time>/` (git-ignored).
A Paid screenshot is not evidence; the report is. Row 9 is changed only after the owner has run this and read the report.

**Tests (none is a sandbox run):** `tests/api/test_internship_onboarding_reconcile_task.py` runs the real `_reconcile()` on a lost-webhook
order (a young order is not touched; after 11 minutes it is confirmed once with one receipt and one email; a second run and a late
webhook change nothing; disabled Cashfree is a no-op), checks the Beat entry and the task registration, and executes the real
`recon.sql` on PostgreSQL (including each way the evidence can be missing or contaminated);
`tests/unit/test_staging_gateway.py` runs the recon gateway rules in a real nginx; `ops/staging-cashfree/tests/recon_test.sh` (30
cases, fake Docker) covers the commands, the report's verdicts, mutual exclusion and every rollback path.

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
   4a-i. The manual button on its own (7b) has now passed with qualifications (4a-iii). Still open, owner's call on whether
   they are needed before a controlled start: the 15-minute reconciliation task against the real sandbox (row 9: the isolated test and its
   report exist, 4a-iv, but it has **not been run**; the lost-webhook recoveries so far were the return page, 4a-ii, and the button), and a real "user dropped" notification (row 6).
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
