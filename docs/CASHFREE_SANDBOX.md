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
| Cloud session access to Cashfree | still blocked (proxy); not needed any more, the sandbox run happens on the Mac |
| Production | untouched; Cashfree stays off there (`CASHFREE_ENABLED` unset) |

## 4a. Sandbox acceptance record

Sources: **Mac** = observed by the owner on the Mac staging stack (2026-11-02/03), as reported; **Test** = automated
test in this repository (mocked Cashfree HTTP, real HMAC signatures, real database). No result below is claimed from a
source it does not list.

| # | Scenario | Result | Source |
|---|---|---|---|
| 1 | ₹2,000 order for the configured fee, hosted checkout, sandbox payment (twice) | passed | Mac |
| 2 | Success webhook -> HTTP 200 -> payment confirmed once -> receipt PDF + email | passed | Mac; Test |
| 3 | Same success webhook delivered again -> HTTP 200, still one payment and one receipt | passed | Mac |
| 3a | Replay adds no second receipt **email**, payment row or accounting entry (exact repeat, re-wrapped copy, status check) | passed in tests (one email queued; the send task also skips a document already sent; onboarding posts nothing to accounting); confirm on the Mac with `./staging.sh evidence` | Test; Mac pending |
| 4 | ₹1 sandbox refund -> refund webhook -> credit note `RCPT-CN-2026-000001` emailed (Mailpit) | passed | Mac |
| 4a | ₹1 refund counted once: ledger = payment 2,000 + refund 1 + waiver 1 (`refund_adjustment`); student owes 1,999 and has paid 1,999 net; balance 0; dashboard received 1,999 | correct by design and tested; the waiver lowers what is owed, the refund lowers what was paid, so the ₹1 is not counted twice; confirm the Mac numbers with `./staging.sh evidence` | Test; Mac pending |
| 4b | Refund idempotency: one open refund per payment (second request 409); one gateway call with an id derived from the refund row; refund-webhook replays (exact and re-wrapped) change nothing; one credit note, emailed once | passed | Test |
| 5 | Failed payment (`testfailure@gocash`) -> no receipt, student can retry with a new order | passed in tests; **sandbox run pending** | Test; Mac pending |
| 6 | Checkout closed / user dropped -> no receipt, stays unpaid, retry possible | passed in tests; **sandbox run pending** | Test; Mac pending |
| 7 | Lost webhook -> recovered by the status check / 15-minute reconciliation, exactly once | passed in tests (stale_orders -> refresh_order; re-running changes nothing); **sandbox run pending** | Test; Mac pending |
| 8 | First checkout stayed on Cashfree's return page, second returned | not reproduced in code; see 4b below | Mac |

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

1. On the Mac: scenarios 5, 6, 7 in the sandbox, then `./staging.sh evidence` with every check at 0 and one email per
   receipt/credit note; record the results in this table.
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
