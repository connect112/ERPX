# Social Media Command Center: implementation report

An AI-assisted Instagram command center inside the ERPX admin site (Social Media page). Written at the end of Phase 6. Everything
below is what the code does today; the "Not verified" section says what has never run against a real Instagram account.

## 1. Status

| Phase | What | State |
|---|---|---|
| 1 | Data model, strategy and settings, draft and approval workflow, CRM lead link | deployed |
| 2 | AI research and studio, source verification, artwork rendering, nine-post grid | deployed |
| 3 | Calendar, durable scheduling, reliable publishing | deployed |
| 4 | Instagram connection, comments and DMs, manual-only replies, webhooks | deployed |
| 5a | Analytics, experiments, weekly and monthly reports | built, tested, awaiting "deploy" (PR #111) |
| 5b | Tracked links, leads made by a person, funnel report, hashtag measurements | built, tested, awaiting "deploy" (PR #112) |
| 6 | Hardening, retention and erasure, job monitoring, accessibility, dependency audit | built, tested (this PR) |

## 2. What a person can do

Tabs on the Social Media page: Overview (daily briefing), Studio (research-backed drafts), Research (official advisories),
Posts, Calendar, Queue, Comments, Messages, Campaigns & Leads, Analytics, Reports (with Experiments), Library, Grid, Strategy,
Settings & Integrations (connection, what Instagram allows, background-job health, privacy and retention, budgets, notifications).

The hard rules the code enforces, each with tests:

- Nothing is published without a recorded approval; an edit after approval needs approval again.
- **No comment reply or direct message is ever sent by anything except a person pressing Send** (one send per request, a record
  before the send, an unclear result is never retried automatically). A test fails if anything other than the reply service calls
  the send functions.
- An AI only drafts. Comments, messages and research text are untrusted data, fenced from the instructions; drafts that state
  prices, dates, guarantees, student results or links are discarded; the AI can raise "handle personally" but never lower it.
- A figure Instagram didn't give is "not available", never zero; every figure shows source, period, last read, observed vs
  calculated, and limits.
- A CRM lead exists only because a person created it; nothing says a post produced an enrolment.
- Tokens are encrypted at rest, sent in a header, never returned by the API, never logged.

## 3. Migrations (in order)

`0069` social media core, `0070` research and AI usage, `0071` assets and artwork, `0072` publishing, `0073` connection and
webhooks, `0074` inbox (media, comments, conversations, messages, replies), `0075` insights, experiments, reports, `0076` tracked
links and lead links, `0077` job heartbeats. Downgrades drop the tables (and their data), so prefer fixing forward.

## 4. Environment variables

Never put these in the repository or in chat; set them in the server environment.

| Variable | Needed for | Notes |
|---|---|---|
| `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET` | connecting, webhooks | from the Meta app |
| `INSTAGRAM_WEBHOOK_VERIFY_TOKEN` | webhooks | any long random string, the same one entered in the Meta app |
| `INSTAGRAM_REDIRECT_URI` | connecting | optional; default `FRONTEND_URL` + `/api/v1/social-media/connect/callback`; must match the Meta app exactly |
| `FRONTEND_URL` | links, redirect, emails | the public https address of the site (tracked links are `FRONTEND_URL/api/v1/social-media/l/<token>`) |
| `AI_API_KEY` (+ `AI_API_BASE_URL`, `AI_MODEL`) | drafts, suggestions, proofreading | without it the screens say AI isn't configured |
| `SOCIAL_AI_INPUT_USD_PER_MTOK`, `SOCIAL_AI_OUTPUT_USD_PER_MTOK`, `SOCIAL_USD_TO_INR` | cost estimates | defaults 3, 15 and 85: placeholders to confirm against the current price list |
| `SOCIAL_IMAGE_API_KEY`, `SOCIAL_IMAGE_API_BASE_URL`, `SOCIAL_IMAGE_MODEL`, `SOCIAL_IMAGE_COST_INR` | AI backgrounds (optional) | deterministic templates work without them |
| `SOCIAL_TOKEN_ENCRYPTION_KEY` | token encryption | optional; if empty the key is derived from `JWT_SECRET_KEY`, so **rotating that secret makes stored tokens unreadable** and Instagram must be reconnected |
| `INSTAGRAM_SCOPES`, `INSTAGRAM_GRAPH_BASE_URL`, `INSTAGRAM_GRAPH_VERSION`, `INSTAGRAM_AUTHORIZE_URL`, `INSTAGRAM_TOKEN_URL` | normally untouched | defaults follow Meta's documentation |

## 5. Meta setup (what is needed before anything is real)

1. The Instagram account must be a Professional account (Business or Creator).
2. At developers.facebook.com create an app (type Business), add the Instagram product, open "API setup with Instagram login".
3. Add the redirect address shown on the Settings page, exactly.
4. Under Roles add the Instagram account as an Instagram tester and accept the invitation in the Instagram app.
5. Webhooks: set the callback address and verify token shown on the Settings page and subscribe to comments and messages. Meta only
   sends notifications once the app is Live.
6. Put the app ID, secret and verify token in the server environment and restart.
7. Press Connect Instagram, then "Check what it can do". For your own account (added as a tester) standard access is enough;
   reading comments and messages for other accounts needs Meta's app review.

## 6. Permissions

`social_media.view` (read everything), `.manage` (edit, make links and reports, run retention), `.approve`, `.publish`, `.connect`,
`.inbox` (read comments and messages), `.reply` (send replies; sending needs `.inbox` too). Creating a lead also needs the CRM's
own `crm.leads.manage` (a follow-up needs `crm.followups.manage`); seeing the list of linked leads needs `crm.leads.view`. Erasing
a person needs `.manage` and `.inbox`. Administrators get all of them from the RBAC seed.

## 7. Scheduled jobs (Celery beat) and how they are watched

| Job | When | What |
|---|---|---|
| `social.publish_due` | every minute | queues posts whose time has come (the database is the schedule) |
| `social.recover_publishing` | every 5 minutes | settles posts left half way by a crash or restart |
| `social.sync_inbox` | every 30 minutes | reads comments and messages (webhooks wake it sooner) |
| `social.sync_insights` | 02:30 UTC daily | reads profile and post figures |
| `social.refresh_tokens` | 03:15 UTC daily | keeps the Instagram access alive |
| `social.make_reports` | 03:30 UTC daily | writes the weekly and monthly report if due (idempotent) |
| `social.apply_retention` | 04:30 UTC daily | removes personal data past the retention period |
| `social.check_health` | every 15 minutes | emails once a day about a job that failed or went quiet |

Each job leaves a heartbeat; Settings shows them, the Overview warns about a stalled job, and the notification addresses get an
email. A job that has never run is "not run yet", not a fault.

## 8. Security, privacy and abuse protection

- Least privilege (above); every route checks permissions; the only public routes are the Meta webhook (signature-checked, ids
  only, rate-limited) and the tracked-link redirect (rate-limited, destination fixed by staff, stores only a daily count).
- Comment, message and reply text, handles and AI drafts never reach the audit trail (`__audit_exclude_fields__`); machine-written
  figures and heartbeats are skipped; no log call carries personal text (a test scans for it).
- Links that come from outside are kept and shown only if they are plain https addresses on the expected site (`safe_url.py`,
  `safeHref`); a test fails if the web code writes HTML or links to an unchecked address.
- The retention period set in Settings is enforced daily: comments, conversations, messages, reply texts (the record of who sent a
  reply stays), posts read and notifications. One person's data can be erased on request (counted first, then confirmed).
- OAuth state is a signed one-use token plus a server nonce; webhook signatures use HMAC-SHA256; uploads are validated; CSRF does
  not apply to the API because it authenticates with a bearer header, not a cookie.
- Dependency check (2026-10-10): `pip-audit` found python-jose 3.3.0 (fix 3.4.0), python-dotenv 1.0.1, aiosmtplib 3.0.2 and pytest
  8.3.3 with known advisories; `npm audit` found axios and react-router advisories. These are shared platform dependencies, so they
  were not changed inside this work; two separate upgrade tasks were raised.

## 9. Accessibility

axe-core (WCAG 2.0/2.1 A and AA plus best practice) was run against every Social Media tab with data loaded, the reply, create-lead,
tracked-link, experiment and conversation dialogs, and in dark mode. It found and this phase fixed: inactive tab labels below the
4.5:1 contrast minimum, a skipped heading level (a hidden section heading was added), and faint out-of-month calendar days. All
now pass. Charts have text alternatives and mark missing days; status is never colour alone. Not covered: a screen-reader session by
a person.

## 10. Tests and results

Run on 2026-10-10 against a local Postgres and MinIO (Docker), with scripted clients and a local imitation of Instagram's API.

- **Whole backend suite** (`pytest tests`): 1,199 passed, 9 failed. All 9 are the backup and restore tests
  (`tests/api/test_backups.py`, `tests/integration/test_restore_backup_integration.py`): they run `pg_dump` and `pg_restore`, which
  are not installed on this Windows machine ("The system cannot find the file specified"). They are unrelated to Social Media and
  need a machine with the PostgreSQL client tools (or the Docker image) to pass.
- **Social Media tests**: 470 across ten files (`tests/api/test_social_media*.py`): core and approval, studio and research,
  artwork and grid, publishing and recovery, connection and webhooks, inbox, replies and AI suggestions, analytics, leads and
  hashtags, and hardening. They cover the areas the brief lists: authorization, connection and missing permissions, token expiry and
  revocation, content editing, rendering and overflow, carousels and the grid, scheduling and time zones (including clock changes),
  restart recovery, publishing failures, ambiguous outcomes and duplicates, webhook signatures and repeats, comment and message
  sync and manual replies, prevention of automatic replies (a test also scans the source), missing and unsupported metrics, lead
  attribution, budget limits, retention and erasure, and rate limits and external failures.
- **Web**: `tsc -b`, eslint and 52 vitest tests pass.
- **Accessibility**: axe-core on every tab and dialog (light and dark): no violations after the fixes in section 9.
- **Browser checks** as a plain Administrator against a local imitation of Instagram: connection, inbox and replies (one send per
  double click, an unclear result), analytics and reports, leads and tracked links, retention and job-health panels, no horizontal
  overflow at 375px.

## 11. Not verified, and live tests that remain blocked

Nothing has run against a real Meta app or Instagram account. Everything was exercised against scripted clients and a local
imitation of Instagram's API. These live checks are blocked until the Meta app exists:

1. The OAuth round trip (authorize, code exchange, long-lived token, `/me`) and daily refresh.
2. "Check what it can do": which capabilities a real account reports.
3. The webhook handshake and a real signed comment or message notification.
4. Publishing a single image, a carousel and a story (container processing time, JPEG requirement, daily quota figure).
5. The "unclear outcome" check against a real profile.
6. Reading comments and replies; posting a comment reply.
7. Reading direct messages and sending one inside the 24-hour window (needs app review beyond testers).
8. Account and post insights: which metrics a real account of this size returns; follower-history snapshots from the first read.
9. A tracked link opened from Instagram's in-app browser (does it count correctly, do previews distort it).
10. A real AI model's draft quality and the real image provider.
11. Email delivery of problem alerts through the real SMTP settings.

The Settings page marks a feature "verified live" only after real use proves it.

## 12. Remaining blockers and pending items

- Meta app and the environment variables above (nothing connects without them).
- The approved Pentrix logo and brand colours (the page says they are placeholders until confirmed).
- Real SMTP "Send test" for the problem emails.
- The shared dependency upgrades noted in section 8.
- Possible later: other platforms (the connection layer is modular but only Instagram is built), AI commentary on reports.

## 13. Estimated operating cost (an estimate, not an invoice)

AI is the only paid part. With the placeholder prices in the settings (3 and 15 US dollars per million input and output tokens, 85 rupees per dollar):

- a drafted post (about 1,500 tokens in, 700 out) is about 1.3 rupees; a rewrite or a proofread is a fraction of that;
- a reply suggestion (about 800 in, 200 out) is about 0.5 rupees;
- an AI background image is budgeted at `SOCIAL_IMAGE_COST_INR` (default 4 rupees); deterministic templates cost nothing.

A month of 30 posts with a couple of rewrites and an AI background each, plus 100 reply suggestions, comes to roughly 250 to 300
rupees. Real spend appears on the Settings page from recorded token counts and stops at the monthly budget you set (a budget of 0
means no limit). The Instagram API itself is free; hosting uses the existing server (no new service), the stored images are a few
megabytes a month, and the daily jobs are light. Confirm the model prices before relying on these figures.

## 14. Deployment (per release)

1. Merge the pull requests in order (5a, 5b, 6 as they are approved).
2. On the server: `git pull`, then rebuild and restart `api`, `web`, `celery_worker` and `celery_beat` (new tasks need the worker
   and beat restarted). The migrations run on API start (`alembic current` should show `0077`).
3. Run the RBAC seed once if a release adds permissions (5a, 5b and 6 add none).
4. Restarting the API drops requests for about a minute: avoid live events.
5. Verify: the new routes answer 401 when logged out, the Settings page lists the jobs, and after a few minutes the jobs show
   "Running".

## 15. Recovery procedures

| What went wrong | What happens by itself | What to do |
|---|---|---|
| The worker or beat container stopped | Scheduled posts wait: the schedule is the database. Settings and the Overview show the jobs as not running; an email is sent once a day | Restart them. A post that is due and less than 60 minutes late goes out on the next minute; one later than that is marked missed and waits for a person (it is never published stale). Publishing interrupted mid-way (a claim older than 10 minutes) is settled by the recovery job within about 15 minutes |
| A post's outcome is unclear (a timeout while publishing) | It is never retried by itself and an identical one is blocked | Queue > Check with Instagram; if it can't settle, look at the profile and choose Resolve |
| A reply's outcome is unclear | Never retried; the same text to the same target is blocked for five minutes | Check with Instagram, or "I looked myself" and record what you saw |
| The Instagram token expired or was revoked | Publishing and reading pause, you are emailed, a daily refresh tries to prevent it | Settings > Reconnect |
| "The stored access token can't be read" | Reading and publishing stop | The encryption key changed (`SOCIAL_TOKEN_ENCRYPTION_KEY` or `JWT_SECRET_KEY`). Restore the key, or reconnect |
| Webhook notifications stopped | The half-hourly read is the safety net | Check the app secret and verify token in the environment and that the Meta app is Live |
| Meta asks for the app secret rotation | Webhooks fail signature checks (403) | Put the new secret in the environment and restart the API |
| Data restored from a backup | Social tables live in the same database as the rest of ERPX | Restore the database and the storage bucket together (artwork lives in the bucket); tokens still work if the encryption key is unchanged |
| Someone asks to be forgotten | n/a | Settings > Privacy and retention > Erase one person's data (then handle any CRM lead in the CRM) |
| Something is publishing that shouldn't | n/a | Disconnect the account in Settings (stops all publishing and reading), or set publishing to manual; pause a tracked link to stop it redirecting |
| A bad migration | n/a | Prefer fixing forward; `alembic downgrade` drops the newest social tables and their data |
