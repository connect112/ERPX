# Isolated staging for the Cashfree SANDBOX run

Purpose: run the real Cashfree sandbox flow (order, hosted checkout, signed webhooks, status checks, refunds) against an
ERPX copy that shares nothing with production: its own Postgres, Redis and MinIO, synthetic data only, all email caught
by Mailpit, sandbox keys only. Nothing here touches AWS, DNS or the production server.

Files: `docker-compose.staging.yml` (layered on the repository's `docker-compose.yml`), `staging.env.example`,
`preflight.sh` (refuses production keys/flags/domains, weak secrets, a tracked env file, or a machine already running
ERPX), `.gitignore` (keeps `staging.env` out of Git).

## Where to run it (owner decision)

| Option | Cost | Needs | Notes |
|---|---|---|---|
| **A. A spare computer with Docker + Cloudflare quick tunnel** (recommended for one validation run) | free | Docker, ~6 GB free disk, internet | public HTTPS URL `https://<random>.trycloudflare.com`, no account and no DNS change; the URL changes whenever the tunnel restarts, so the Cashfree webhook URL is set for the session |
| B. A separate small EC2 instance (e.g. t4g.small/t3.small, 30 GB gp3) + a staging host name | roughly US$15-20 per month while running (stop it between runs) | your approval for paid AWS resources and a DNS record (e.g. `staging.<domain>`), or the quick tunnel instead of DNS | stable URL; never the production instance (fixed container names would collide with production's) |

Not suitable: this Claude Code cloud session (no inbound HTTPS, and Cashfree hosts are blocked by its network policy),
or the production server.

## Run (option A)

```bash
git clone https://github.com/connect112/ERPX.git erpx-staging && cd erpx-staging
cp ops/staging-cashfree/staging.env.example ops/staging-cashfree/staging.env   # fill it in yourself; never paste keys anywhere else
```

```bash
docker run -d --name erpx_staging_tunnel --add-host=host.docker.internal:host-gateway cloudflare/cloudflared:2024.12.2 tunnel --no-autoupdate --url http://host.docker.internal:80
```

```bash
docker logs erpx_staging_tunnel 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | head -1   # put this in STAGING_PUBLIC_URL
```

```bash
bash ops/staging-cashfree/preflight.sh
```

```bash
docker compose -p erpx-staging -f docker-compose.yml -f ops/staging-cashfree/docker-compose.staging.yml --env-file ops/staging-cashfree/staging.env up -d postgres redis minio api celery_worker celery_beat web nginx mailpit
```

Then, in the Cashfree dashboard (Test mode): Developers > Webhooks, endpoint
`<STAGING_PUBLIC_URL>/api/v1/public/payments/cashfree/webhook`, version matching `CASHFREE_API_VERSION`, events: payment
success, payment failed, payment user dropped, refund status (and auto refund if offered); whitelist the tunnel domain
if the dashboard asks. Mail viewer: `http://127.0.0.1:8025` on that computer.

Sign in with the seed account once, create a plain **Administrator** user (not Super Admin) and do the run with it.
Create one synthetic institution, student and internship (no production data).

## Validation run (record each result in docs/INTERN_ONBOARDING_PROGRESS.md)

Adapter checks against the real sandbox (the api container has pytest and the sandbox keys; the tests are mounted in):

```bash
docker compose -p erpx-staging -f docker-compose.yml -f ops/staging-cashfree/docker-compose.staging.yml --env-file ops/staging-cashfree/staging.env run --rm -e CASHFREE_SANDBOX_TESTS=1 -v "$PWD/tests:/app/tests" -v "$PWD/pytest.ini:/app/pytest.ini" api python -m pytest tests/sandbox -q
```

They cover: an order for the configured INR 2,000 with a payment session, order-id reuse refused, unpaid refund refused,
wrong keys refused without the secret appearing anywhere.

In the browser (Cashfree's sandbox test data: UPI `testsuccess@gocash` succeeds, `testfailure@gocash` fails; card OTP
`111000`; check the sandbox data page for current values):

1. Internship: hybrid, payment on, method "Online (Cashfree)", fee left at INR 2,000, closing date; send the test student
   their link (the email arrives in Mailpit).
2. Student: details, documents, accept, **Pay ₹2,000.00 online**: Cashfree's checkout opens -> pay with `testsuccess@gocash`.
   Expect: webhook confirms once, student shows paid, one receipt PDF and its email, completion once documents are
   verified; LMS access per the internship's rule.
3. Duplicate: Cashfree dashboard "resend webhook" -> acknowledged as duplicate / already recorded; nothing changes.
4. Failure: second student pays with `testfailure@gocash` -> no receipt, can retry with a new order.
5. Cancellation: third student closes the checkout page -> user-dropped/pending, no receipt; "I have paid: check status"
   and the 15-minute reconciliation keep it unpaid.
6. Lost webhook: remove (or disable) the webhook endpoint in the Cashfree dashboard, pay with a fourth student, then
   "I have paid: check status" -> confirmed through the status check; add the endpoint back. (Do not restart the tunnel
   for this: a quick tunnel gets a new random URL on every start.)
7. Refund: finance refunds ₹1.00 of the paid order -> Cashfree refund -> refund webhook -> credit note. Then
   the same `pytest tests/sandbox` command with `-e CASHFREE_SANDBOX_PAID_ORDER_ID=<order> -e CASHFREE_SANDBOX_REFUND=1`.
8. Optional: repeat 2 with `CASHFREE_API_VERSION=2026-01-01` (Cashfree's latest) before choosing it for production.

## Tear down

```bash
docker compose -p erpx-staging -f docker-compose.yml -f ops/staging-cashfree/docker-compose.staging.yml --env-file ops/staging-cashfree/staging.env down -v
```

```bash
docker rm -f erpx_staging_tunnel
```

Then remove the webhook endpoint from the Cashfree dashboard and delete `staging.env`.
