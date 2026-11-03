# Cashfree SANDBOX staging on a Mac (Apple Silicon)

A throwaway, isolated ERPX for running the real Cashfree **sandbox** flow (order, hosted checkout, signed webhooks,
status checks, refunds). It shares nothing with production or with any other ERPX stack on the Mac, uses synthetic data
only, catches every email locally, and accepts Cashfree **Test-mode** keys only. Nothing here touches AWS, DNS or the
production server, and no real money can move.

## What is isolated, and how

| Concern | How |
|---|---|
| Names | Docker Compose project `erpx-cf-staging` (in `compose.yml`): every container, network and volume is prefixed with it; there are no fixed `container_name`s, so another ERPX stack (e.g. `erpx_api`) never collides |
| Data | its own Postgres (`erpx_staging`), Redis and MinIO, each on its own volume; the database starts empty and is migrated from scratch |
| Network | its own Docker network `erpx-cf-staging_default` on a dedicated subnet (`STAGING_SUBNET`, default `10.213.47.0/24`), created by `./staging.sh` and declared `external` in `compose.yml`, so Compose never compares, recreates or removes it (see "Why the network is external"); preflight refuses it if it overlaps any other Docker network on the Mac (other projects included), a LAN/VPN address of the Mac, or Docker Desktop's internal `192.168.65.0/24` |
| Ports | only two, both on `127.0.0.1`: the gateway (`STAGING_HTTP_PORT`, default 8080) and the Mailpit viewer (`STAGING_MAIL_PORT`, default 8025). Postgres, Redis, MinIO, the API and Celery publish nothing |
| Internet exposure | a Cloudflare quick tunnel (`https://<random>.trycloudflare.com`) forwards to the gateway only. The gateway serves the web app, `/api/` (staff screens, student page, Cashfree webhook) and `/_files/` (short-lived signed file links); it hides `/api/docs`, `/api/redoc`, `/api/openapi.json` and `/metrics` |
| Email | all mail goes to Mailpit (viewer on `127.0.0.1` only); nothing is sent |
| Cashfree | `CASHFREE_ENV=sandbox`, `CASHFREE_ALLOW_PRODUCTION=false` fixed in `compose.yml`; preflight refuses keys that do not look like Test-mode keys |
| People | synthetic organizations, administrator and students (`@example.com`) from `seed_synthetic.py`; never production data |
| Secrets | `staging.env` is generated with fresh random values, kept at mode 600, git-ignored; preflight checks no value appears in any tracked or staged file |

`preflight.sh` (run automatically before `tunnel` and `up`) stops on any of these:
- Docker not running or Compose older than 2.20; less than 4 GB memory for Docker;
- `staging.env` missing, tracked by Git or not git-ignored;
- unexpected settings in it (e.g. `DATABASE_URL`, `AWS_*`), or production hosts (`pentrix.in`, `amazonaws.com`, `shared_postgres`, `api.cashfree.com`, ...);
- shell variables that would override `staging.env`;
- live-looking Cashfree keys or keys in an unrecognised format;
- weak or default secrets, or any secret found in tracked/staged files;
- a public address that is not `https://`;
- a port already used by another program or container;
- a `STAGING_SUBNET` that is not a private /16-/28 range or overlaps another network, or this stack's existing network on a different subnet (an existing network on the same subnet is kept as it is);
- a `compose.yml` that does not declare the network `external` (or defines `ipam`);
- settings not documented in `staging.env.example` (the allowed list is read from that file, so a newly documented setting never trips it);
- any published port not bound to `127.0.0.1`, a fixed container name, or Cashfree/ENVIRONMENT not sandbox/staging in every backend service.

## Requirements (MacBook Pro M3 Pro)

- macOS with **Docker Desktop** (Apple Silicon build), Compose 2.20 or newer (any current Docker Desktop).
- Docker Desktop > Settings > Resources: **6 GB memory or more** (8 GB recommended), 4 CPUs.
- About **10 GB free disk** (images ~4 GB, build cache, small volumes). First build: about 5-10 minutes.
- `git`, `curl`, `openssl` (built into macOS / Xcode command line tools).
- Every image is multi-arch (`linux/arm64` native): `postgres:16-alpine`, `redis:7-alpine`,
  `pgsty/minio:RELEASE.2026-08-04T00-00-00Z`, `axllent/mailpit:v1.21`, `nginx:1.27-alpine`,
  `cloudflare/cloudflared:2025.4.0`; the two ERPX images are built on the Mac from `python:3.12-slim` and
  `node:20-alpine`. Every Python dependency has an arm64 wheel except `svglib`, which is pure Python.
- MinIO: the official `minio/minio` image can no longer be pulled (MinIO stopped publishing community images in
  October 2025), so this kit uses the maintained community build `pgsty/minio` (pinned). To use another
  S3-compatible MinIO image instead, set `STAGING_MINIO_IMAGE` in `staging.env`.

## Set up and run

From a fresh clone (any folder; it does not need to be near another ERPX checkout):

```bash
git clone https://github.com/connect112/ERPX.git ~/erpx-cf-staging
```

```bash
cd ~/erpx-cf-staging && git checkout claude/cashfree-sandbox-readiness && cd ops/staging-cashfree
```

1. Create `staging.env` with fresh staging-only secrets (prints no values):

```bash
./staging.sh init
```

2. Add your Cashfree **Test-mode** keys (Cashfree dashboard > switch to Test mode > Developers > API Keys) in a text
   editor. Fill `CASHFREE_APP_ID` and `CASHFREE_SECRET_KEY`, save, close. Do not paste them anywhere else.

```bash
open -e staging.env
```

3. Start the tunnel; it prints the public address and the webhook URL and saves the address in `staging.env`:

```bash
./staging.sh tunnel
```

4. Build and start everything (runs preflight first; waits until the API is ready; creates the storage bucket):

```bash
./staging.sh up
```

5. Create the synthetic organizations, the plain Administrator and the students:

```bash
./staging.sh seed
```

6. Check isolation, routing, file links, migrations, sandbox mode and organization scoping:

```bash
./staging.sh verify
```

7. Check the adapter against the real Cashfree sandbox (creates sandbox orders only):

```bash
./staging.sh sandbox-tests
```

Then in the Cashfree dashboard (Test mode) > Developers > Webhooks, add the webhook URL printed by step 3
(`<public address>/api/v1/public/payments/cashfree/webhook`), version `2025-01-01`, events: payment success, payment
failed, payment user dropped, refund status (and auto refund status, if offered). Whitelist the tunnel's domain if the
dashboard asks.

Sign in at the public address as `staging-admin@example.com` (password: `STAGING_ADMIN_PASSWORD` in `staging.env`;
a plain Administrator of "Staging Org A", not a Super Admin). Mail: `http://127.0.0.1:8025`.

## Validation run (record each result in docs/INTERN_ONBOARDING_PROGRESS.md)

Cashfree sandbox test data (check Cashfree's sandbox page for current values): UPI `testsuccess@gocash` succeeds,
`testfailure@gocash` fails; card OTP `111000`.

1. Our Internships > "Sandbox Internship (synthetic)" > Onboarding Settings: hybrid, payment on, method "Online
   (Cashfree)", fee left at INR 2,000, a closing date. Onboarding: send a synthetic student their link (it arrives in
   Mailpit).
2. Student: details, documents, accept, **Pay ₹2,000.00 online** -> Cashfree checkout -> `testsuccess@gocash`.
   Expect: the webhook confirms once, the student shows paid, one receipt PDF and its email (Mailpit), completion once
   documents are verified, LMS access per the internship's rule.
3. Duplicate: Cashfree dashboard "resend webhook" -> acknowledged as duplicate / already recorded; nothing changes.
4. Failure: another student pays with `testfailure@gocash` -> no receipt; they can retry with a new order.
5. Cancellation: another student closes the checkout -> no receipt; "I have paid: check status" and the 15-minute
   reconciliation keep it unpaid.
6. Lost webhook: disable the webhook in the dashboard (or make the gateway refuse it), pay with another student ->
   ERPX confirms the payment from its own status check, once. Two things can do that before you press anything: the
   student's return page (`?order=...` runs the same check on load) and the 15-minute reconciliation. To test the button
   itself, close the Cashfree page without returning, open the student link without `?order=`, and press "I have paid:
   check status" within 10 minutes of creating the order. Then enable the webhook again and expect the late
   notifications to be acknowledged (200) without a second payment or receipt. (Do not restart the tunnel for this: it
   would get a new address.)
7. Refund: finance refunds ₹1.00 of the paid order -> Cashfree refund -> refund webhook -> credit note. Then, with that
   order's id:

```bash
PAID_ORDER=<order id> REFUND=1 ./staging.sh sandbox-tests
```

8. Optional: set `CASHFREE_API_VERSION=2026-01-01` in `staging.env`, run `./staging.sh up`, repeat step 2.

## Evidence (before any change to the running stack)

```bash
./staging.sh evidence
```

Saves a read-only snapshot to `ops/staging-cashfree/evidence/<UTC time>/` (git-ignored): payment orders, the full
ledger, net per student, receipts and credit notes with their email status, every Cashfree notification's outcome (no
signatures or bodies are stored anywhere), timeline events, every Mailpit message as `.eml`, and emails per subject. It
also prints the checks that must all be 0: a Cashfree payment recorded twice, a document issued twice, a confirmed
payment/refund without its document, a refund adjustment without its refund, and accounting journal entries (onboarding
never posts any). A receipt or credit-note subject listed twice would mean a duplicate email.

## Applying a new tunnel address to a running stack

A quick tunnel gets a new address whenever it restarts. To point a stack that is already running at the new address
without stopping the databases, storage, mail, web or gateway:

```bash
./staging.sh network-check
```

(read-only: shows the network, its subnet, what is attached, and that Compose treats it as external), then:

```bash
./staging.sh tunnel
```

(starts only the tunnel container if it is not running, saves its current address in `staging.env`), then:

```bash
./staging.sh refresh-app
```

`refresh-app` runs preflight, then restarts **only** `api`, `celery_worker` and `celery_beat` (the services that read
`STAGING_PUBLIC_URL`: frontend links, CORS, the Cashfree return URL), reloads the gateway's nginx so it finds the
restarted API, waits until the API is ready and prints the `FRONTEND_URL` the API now uses. Postgres, Redis, MinIO,
Mailpit (and their volumes), web, the gateway and the tunnel keep running. Finally update the webhook URL in the
Cashfree dashboard to the one printed. Unpaid orders created earlier keep the old return address (see Troubleshooting).

## Why the network is external

Compose 2.40 and newer stores a hash of a network's definition on the network and, when a later `up` finds a different
hash, stops the services it was asked to start and tries to remove the network before recreating it. On a running stack
that cannot work (the databases are still attached): `up -d --no-deps --force-recreate api` stopped the API, failed with
"network ... has active endpoints", and left the site returning 502. A network created by an older `compose.yml`
(before `STAGING_SUBNET` existed) has a different hash than the current definition even when the subnet is the same.
Declaring the network `external` in `compose.yml` makes Compose only look it
up; `./staging.sh` creates it (once, on `STAGING_SUBNET`) and removes it only in `recreate-network` and `destroy`, and
only if it is this project's and nothing is attached. Your existing network, subnet and data are used as they are.

If the API container was recovered by hand (`docker network connect ...` then `docker start ...`), `refresh-app` replaces
it with a clean container from the compose definition (with the right network alias and the new address); a container connected with a plain
`docker network connect` may lack the `api` alias the gateway looks up.

## Moving a stack to a different subnet

Not needed to keep the subnet the network already has: set `STAGING_SUBNET` to it in `staging.env` (preflight then says
"kept as it is"). Only to **change** the subnet: **save evidence first** (the command below does it again anyway), then:

```bash
./staging.sh recreate-network
```

It saves evidence, stops and removes this project's containers, then removes the (now empty) network; it refuses to remove
a network that is not this project's or still has anything attached. The database, Redis, MinIO and Mailpit volumes stay.
Then `./staging.sh tunnel`, `./staging.sh up` (creates the network on the new subnet), and update the webhook URL in the
Cashfree dashboard (a new tunnel address).

## Day to day

```bash
./staging.sh status
```

```bash
./staging.sh logs api
```

```bash
./staging.sh network-check
```

```bash
./staging.sh down
```

`down` stops everything and keeps the data. A quick tunnel gets a **new address** each time it starts, so after
`down`: run `./staging.sh tunnel`, then `./staging.sh up`, and update the webhook URL in the Cashfree dashboard.
When the stack is still running and only the address changed, use `./staging.sh refresh-app` instead of `up`.
Keep the tunnel running only while you test.

## Clean up (this project only)

```bash
./staging.sh destroy
```

After you type `erpx-cf-staging` to confirm, it removes this project's containers, network and volumes (its database,
Redis and MinIO data) and its two locally built images (`erpx-cf-staging/api:local`, `erpx-cf-staging/web:local`).
Shared base images (postgres, nginx, ...) and every other Docker project are left alone. Then delete `staging.env` and
remove the webhook endpoint from the Cashfree dashboard. To confirm nothing is left:

```bash
docker ps -a --filter label=com.docker.compose.project=erpx-cf-staging
```

## Testing the scripts on the Mac

The scripts run under macOS's `/bin/bash` (bash 3.2). Two suites run the real `preflight.sh` and `staging.sh` with a fake
`docker` in a throwaway git repository, so they touch no container, network, volume or `staging.env`:

```bash
/bin/bash ops/staging-cashfree/tests/preflight_test.sh
```

(allowed and unexpected settings, CRLF, an existing `STAGING_SUBNET`, the kept validations, the external-network rule), and

```bash
/bin/bash ops/staging-cashfree/tests/upgrade_test.sh
```

(an already-running stack whose network has a stale Compose hash and the databases attached: `refresh-app`, `tunnel`,
`up` and `network-check` must never create, change or remove the network; `recreate-network` removes only an empty one;
a control case reproduces the original failure so a regression would be caught). The fake models Compose's behaviour from
its source; the final proof is `./staging.sh network-check` and `./staging.sh refresh-app` on the real stack.

## Troubleshooting

- The browser stays on Cashfree's page after paying: the return address is fixed when the order is created
  (`<public address>/internship-onboarding?order=...`), and an unpaid order is reused for up to 30 minutes. If the
  tunnel address changed (tunnel restarted, or the order was created before `./staging.sh up` picked up the new
  address), Cashfree sends the browser to an address that no longer exists. The payment itself is still confirmed by
  the webhook or the status check; open the student's link again. Avoid restarting the tunnel during a test.

- 502 from the gateway after the API was restarted by hand: nginx looks up `api` only when it loads its configuration, so
  `docker compose ... exec gateway nginx -s reload` (or `./staging.sh refresh-app`, which does it) fixes it.
- "network erpx-cf-staging_default declared as external, but could not be found" (running `docker compose` directly):
  run through `./staging.sh`, which creates the network.
- Port already in use: set `STAGING_HTTP_PORT` / `STAGING_MAIL_PORT` in `staging.env` to free ports, then `./staging.sh up`.
- "keys do not look like Test-mode keys": Cashfree Test-mode App IDs start with `TEST` and secret keys contain
  `_test_`. Copy the keys from Test mode, not Live. Only if Cashfree changes this format, add
  `STAGING_CASHFREE_KEY_CHECK=relaxed` to `staging.env` (production use is still refused by `CASHFREE_ENV=sandbox`).
- Shell variables override `staging.env`: run `unset CASHFREE_APP_ID CASHFREE_SECRET_KEY ...` as preflight lists.
- The API is not ready after 10 minutes: `./staging.sh logs api` (the first start runs every migration).
