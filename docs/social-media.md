# Social Media module

The **Social Media** page (Marketing section of the admin site, `/social-media`) plans, reviews and approves Instagram
content. It is built in phases; this page records what exists, the rules the code enforces, and what is still to come.

## Rules the code enforces

- **Nothing is published without a recorded approval.** A post becomes `approved` only through an explicit approval by
  someone with `social_media.approve`, with its warnings acknowledged. The approval stores a hash of exactly what was
  approved; any edit to the content, format, sources or schedule withdraws it. Publishing refuses a post whose content
  no longer matches the hash.
- **The publishing states can't be reached from the API.** `scheduled`, `publishing`, `published`, `failed` and
  `publish_unknown` are only ever set by the publisher (Phase 3). A post in one of them can't be edited, deleted or
  moved by a person.
- **Replies to comments and DMs are never automatic.** The module has no code path that sends a reply; AI may only
  classify and suggest. Every reply is typed and sent by a person with an explicit action (Phase 4).
- **Unverified claims can't be approved.** Posts with `unverified`, `conflicting` or `outdated` claims are blocked;
  high-risk or time-sensitive posts need the approver to confirm they checked the sources themselves.
- Access tokens (Phase 4) are stored encrypted, are excluded from the audit trail, and are never returned by the API.

## Phase 1

| Part | Where |
|---|---|
| Data model: `social_settings`, `social_accounts`, `social_posts` (migration 0069) | `modules/social_media/models.py` |
| Strategy and settings: brand, voice, colours (placeholders until confirmed), content pillars, personas, prohibited claims, objectives, design rules, timezone, publish policy, budgets, notifications, retention | `GET/PUT /api/v1/social-media/settings` |
| Draft, review and approval workflow, duplication | `/api/v1/social-media/posts…` |
| Daily briefing with post counts and CRM leads whose source is "Social media" | `GET /api/v1/social-media/overview` |
| Honest capability matrix (what Meta offers, what is built, nothing verified live) | `GET /api/v1/social-media/integration` |

Permissions (granted to the Administrator role automatically): `social_media.view`, `social_media.manage`,
`social_media.approve`. After deploying, run the RBAC seed so the permissions exist (`seed_default_rbac`).

Notes:
- The repository holds no Pentrix logo (only the "GIR Technologies" one), and the brand colours are placeholders.
  The approved logo is uploaded with the artwork renderer in Phase 2.
- Changes to these tables are recorded by the application-wide audit hooks.

## Phase 2a: research, AI studio and fact checks

| Part | Where |
|---|---|
| Research from official sources: CISA advisories feed, CISA Known Exploited Vulnerabilities, NVD (one CVE at a time). Cached with publication and retrieval dates; a source that can't be reached is reported, never filled in | `modules/social_media/research.py`, `GET/POST /social-media/research…` |
| AI drafting (image, carousel, Reel concept, Story) from the brand strategy and selected research, and rewriting one element (hooks, headline, caption, CTA, hashtags, cover text, visual direction, alt text) | `studio.py`, `POST /social-media/studio/generate`, `POST /posts/{id}/regenerate` |
| Automated checks, run on every draft and on demand ("Check facts & rules") | `checks.py`, `POST /posts/{id}/check` |
| Content history: near-duplicate captions, repeated hooks, overused hashtags, topic mix against the pillar targets | `history.py`, `GET /social-media/history` |
| Estimated AI cost, monthly budget (0 = no limit) with an alert, shown under Settings | `usage.py`, `GET /social-media/usage` |

What the checks do: look every CVE up in NVD (exists, CVSS score, rejected) and compare the post's claims (CVSS number,
"critical", "actively exploited" against CISA KEV); require an official, dated, recent source for time-sensitive
posts; flag promises we never make (guaranteed placement, salary or virality) and course fees, batches or student
claims that must come from verified data; enforce the design limits; note that a Reel concept is not a video.
A CVE that an official source the post is built on cites, but NVD doesn't have yet, is a warning; one nobody cites
is a blocking conflict. Checks never approve anything: they can only flag, downgrade the verification status
(`unverified`, `conflicting`, `outdated`) and withdraw an approval whose claims no longer hold.

How the studio stays safe:
- Research text is untrusted. The model only sees it inside a data block that its instructions say contains no
  instructions; the studio can only save a DRAFT, so text in a source cannot approve, schedule or publish anything.
  Instruction-like wording in a source is flagged on the item and on the post.
- The model is told to use only facts present in the sources, and to write evergreen content when there are none.
  It is never asked for links: a draft's sources are the research items that were selected, with their dates.
- Hashtags are labelled "AI-suggested, not a measured trend"; the suggested time is labelled a default assumption
  until real performance data exists (Phase 5).
- Only fixed official hosts are fetched (CISA, NVD); responses are size-capped; XML with a DOCTYPE is refused.

Environment variables (all optional): `AI_API_KEY` (already used by other AI features), `SOCIAL_AI_INPUT_USD_PER_MTOK`,
`SOCIAL_AI_OUTPUT_USD_PER_MTOK`, `SOCIAL_USD_TO_INR` (prices behind the cost estimate; defaults are placeholders to
adjust to your provider's rates). Migration 0070. No new permissions.

## Phase 2b: artwork, image library and the nine-post grid

| Part | Where |
|---|---|
| Deterministic artwork: four templates (editorial, statement, photo, screenshot) on 4:5 posts, carousel slides and 9:16 Story / Reel covers. Every word and the logo are drawn by code with the bundled Inter font | `render.py` |
| Validation on every render: text fits at a readable size (an over-long text is refused, never clipped), contrast against the lightest and darkest parts behind the text, headline length and cover text from the design rules, safe area for Stories and Reel covers | `render.py`, shown in the artwork dialog |
| Image library: approved logo, photographs, real screenshots. Uploads are size-capped, decoded and re-encoded by the server (metadata dropped), SVG refused | `assets.py`, `/social-media/assets` |
| The logo is placed pixel for pixel (only scaled; empty transparent margins trimmed). On a dark design it sits on a light chip | `render.py` |
| Optional AI backgrounds for the Photo template: only the picture is generated; it is darkened under a scrim, stored as synthetic and labelled; only inline image data is accepted (no links are fetched) | `image_provider.py`, `artwork.py` |
| Design and render are separate: change only the wording and it redraws from the stored picture; "new background" replaces only the picture; "remove artwork" keeps the design | `artwork.py` |
| Artwork is part of approval: the approved hash covers the design and rendered files; a render's fingerprint records the exact text and design it shows, so words changed after drawing block approval until redrawn; artwork that breaks the design rules blocks approval | `service.py` (`content_hash`), `checks.py` |
| Optional AI proofread of the words drawn on the artwork (cost counted) | `POST /posts/{id}/proofread` |
| Nine-post grid: colour/layout repetition, abrupt light-dark jumps, repeated headlines or near-identical artwork (perceptual hash), dense text, inconsistent logo, type scale. Shown in the Grid tab, in the artwork dialog and in the approval dialog. The live profile is not readable until the account is connected, and the preview says which posts are missing | `grid.py`, `GET /social-media/grid` |

Environment variables for AI backgrounds (all three must be set; otherwise the feature says it isn't set up):
`SOCIAL_IMAGE_API_KEY`, `SOCIAL_IMAGE_API_BASE_URL`, `SOCIAL_IMAGE_MODEL` (any `/v1/images/generations` compatible API that
returns `b64_json`), and optionally `SOCIAL_IMAGE_COST_INR` (estimated cost per image, for the budget). Migration 0071.
Small shared changes: `upload_bytes` / `read_bytes` on the storage client, the `SOCIAL_IMAGE_*` settings. Font: Inter
(SIL Open Font License, licence file alongside it in `modules/social_media/fonts`).
Note: approval hashes now include the design and artwork, so a post approved before this release has a hash made the
old way; nothing reads that hash until publishing exists (phase 3), and re-approving fixes it.

## Phase 3: calendar, scheduling and publishing

States a post moves through: `draft -> review -> approved -> scheduled -> publishing -> published`, with `failed`, `cancelled`
and `publish_unknown` (the outcome couldn't be confirmed). A person approves; a person with the new `social_media.publish`
permission schedules or publishes (separation of duties). Whether approved posts may be scheduled or only published by hand
is the "After a post is approved" setting. The planned time is not part of what was approved, so moving it keeps an approval.

| Part | Where |
|---|---|
| Calendar (month, week, day, in the account timezone; clock-change times are refused), "approved, not scheduled" list, schedule/move/unschedule/publish-now dialog showing the exact caption and everything that blocks | `publish_routes.py`, Calendar tab |
| Queue: scheduled, publishing, failed and unclear posts with their attempts; retry, check with Instagram, resolve by hand | Queue tab |
| The publisher: atomic claim of due posts, JPEG conversion, containers, publish, permalink | `publisher.py` |
| Instagram client (Authorization header only, errors sorted into transient / permanent / token / ambiguous) | `instagram.py` |
| Encrypted token storage (Fernet, key from `SOCIAL_TOKEN_ENCRYPTION_KEY` or derived from the JWT secret) | `token_crypto.py` |
| Celery: `social.publish_due` every minute, `social.recover_publishing` every five, problem emails | `tasks.py`, `celery_app.py` |
| Every try is recorded (what was sent, what Instagram said, when) | `social_publish_attempts`, `GET /posts/{id}/attempts` |

Reliability rules (all covered by tests with a scripted Instagram):
- **The database is the schedule.** Nothing lives in the queue: a restart or deployment loses nothing. Posts are claimed with one
  atomic UPDATE, so two workers can never take the same post, even if it is queued twice.
- **No duplicate posts.** Creating containers can be repeated safely (and a retry reuses the ones already made). The call that
  creates the post is preceded by a committed note on the attempt. After that, an unclear answer (timeout, dropped connection,
  server error) is never retried blindly: the container's status and the profile's recent posts are checked first. If that settles
  it the post is marked published, or retried because Instagram confirms it wasn't. If it can't be settled the post becomes
  `publish_unknown`, is never sent again by itself, is emailed, and waits for "Check with Instagram" or a person's resolution.
- **Published means Instagram answered** with the new media id, or the check proves it is on the profile.
- **Retries** for temporary problems wait 1, 2, 4, 8, 16 minutes (capped at 30) with jitter, up to five attempts, then fail with the
  last reason and an email. Permanent problems (picture rejected, permission missing) fail at once. An expired or revoked token
  marks the account as needing reconnection instead of looping.
- **Recovery** every five minutes: a post stuck in `publishing` after a crash is put back if nothing had been sent, or checked
  against Instagram if the post-creating call may have been sent; unsettled for an hour it goes to a person.
- **Stale or changed content is never published.** A post that wakes up more than an hour late is failed as "missed" (not
  published stale) and emailed. Just before publishing, the approval hash, the artwork, and the facts (NVD, CISA) are checked
  again; a post whose claims turned wrong or can't be rechecked is paused or retried, not published.
- Every outcome other than a normal success is a status, an attempt record and, for problems, an email to the addresses in Settings.

Configuration (all optional): `INSTAGRAM_GRAPH_BASE_URL` (default `https://graph.instagram.com`), `INSTAGRAM_GRAPH_VERSION`
(default `v25.0`; Meta retires old versions), `SOCIAL_TOKEN_ENCRYPTION_KEY`. Images are converted to JPEG (the only format
Instagram accepts) and fetched by Instagram from `FRONTEND_URL` + the storage proxy path, so that address must be public.
Migration 0072. After deploying: run the RBAC seed (new permission `social_media.publish`) and rebuild/restart the Celery
worker and beat so the new tasks and schedule are picked up.

**Not verified:** nothing here has run against a real Instagram account. The client is written from Meta's documentation
(container status values, JPEG only, up to 10 carousel items; Meta's page states the daily limit as both 50 and 100, so the quota
is read from the API, not hard-coded). Reels can't be published (no video). Posting needs the account connection (phase 4).

## Phase 4a: connecting Instagram

| Part | Where |
|---|---|
| Connect, reconnect, disconnect, check what the account can do, renew the token (Settings tab). Connecting needs the new `social_media.connect` permission | `connect_routes.py`, `connection.py`, `oauth.py` |
| Instagram login: authorize address, a signed one-use link (10 minutes) tied to the person and organisation that started it, code exchanged for a short-lived then a long-lived (about 60 days) token on the server | `oauth.py` |
| The token is stored encrypted, never returned, never logged (the HTTP client's request log has tokens, codes and secrets removed) | `token_crypto.py`, `oauth.py` |
| After connecting, each feature is probed (publishing quota, media, conversations) and recorded as available, unavailable or "needs Meta app review"; the webhook is subscribed to the granted fields | `connection.py` |
| Daily renewal of tokens within 20 days of expiry (Instagram refreshes tokens at least a day old); a token that can't be kept alive marks the account and emails the people in Settings | `social.refresh_tokens` |
| Webhook endpoint `GET/POST /social-media/webhooks/instagram`: verification token checked in constant time; every notification's `X-Hub-Signature-256` (HMAC-SHA256 of the raw body with the app secret) checked before the body is read; size capped; retries recognised and ignored; ids only are kept, never message text | `connect_routes.py`, `social_webhook_events` |
| "Verified" in the capability list now means proven by real use (a post published, a notification received); a passed permission check is shown separately | `routes.py` |

Environment (all optional until you connect): `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`, `INSTAGRAM_WEBHOOK_VERIFY_TOKEN`,
`SOCIAL_TOKEN_ENCRYPTION_KEY` (already in `docker-compose.prod.yml` as pass-throughs), and rarely `INSTAGRAM_REDIRECT_URI`,
`INSTAGRAM_SCOPES`. Migration 0073. New permissions: `social_media.connect`, `social_media.inbox`, `social_media.reply`
(the last two arrive with the inbox; the seed creates all three). After deploying: run the RBAC seed and restart the Celery
worker and beat (new daily task).

Meta setup, in order: (1) Professional Instagram account; (2) developers.facebook.com, create a Business app, add Instagram,
"API setup with Instagram login"; (3) add the redirect address shown on the Settings page, exactly; (4) add the account under
Roles as an Instagram tester and accept the invitation in the Instagram app; (5) Webhooks: the callback address and your verify
token shown on the Settings page, subscribe to comments and messages (the app must be Live to receive them); (6) put the app ID,
secret and verify token in the server's `.env` and restart; (7) press Connect Instagram. For an account you own or manage and have
added to the app, standard access is enough; other accounts need Meta's app review.

**Not verified:** none of this has run against a real Meta app. Meta's documentation doesn't spell out some response shapes
(the `/me` fields, the webhook payload for comments and messages), so those are read defensively and anything unrecognised is
ignored. The first real connection is the real test; the Settings page shows exactly which step failed.

## Phases still to build

4b. Comments and direct messages (read, classify, suggest, and reply by hand only), and acting on webhook notifications.
5. Analytics, hashtag and trend research, reports, lead attribution (trackable links and UTM parameters).
6. Hardening, recovery procedures, cost controls, accessibility, full regression tests.

## Meta setup (needed from Phase 4)

1. The Instagram account must be a Professional account (Business or Creator).
2. Create a Meta developer app and add the Instagram product (<https://developers.facebook.com/docs/instagram-platform/>).
3. Add the account as a tester and request only the permissions needed; reading and replying to comments and messages,
   and publishing, for accounts beyond your own testers need Meta app review.
4. Point the app's redirect and webhook URLs at this site.
5. App ID, secret and verify token go in the server environment (INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET, INSTAGRAM_WEBHOOK_VERIFY_TOKEN); never in the repository or in chat.

Until an account is connected and each feature is exercised against it, the page labels everything "not verified live".
