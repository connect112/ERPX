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

## Phase 1 (this release)

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

## Phases still to build

2. AI research and content studio, source verification, artwork rendering (typography drawn by code, never by an image
   model), nine-post grid preview, optional AI backgrounds.
3. Calendar, durable scheduling, publishing with idempotency and reconciliation of unclear outcomes.
4. Instagram connection (Meta app), comments and DMs, webhooks, manual-only replies.
5. Analytics, hashtag and trend research, reports, lead attribution (trackable links and UTM parameters).
6. Hardening, recovery procedures, cost controls, accessibility, full regression tests.

## Meta setup (needed from Phase 4)

1. The Instagram account must be a Professional account (Business or Creator).
2. Create a Meta developer app and add the Instagram product (<https://developers.facebook.com/docs/instagram-platform/>).
3. Add the account as a tester and request only the permissions needed; reading and replying to comments and messages,
   and publishing, for accounts beyond your own testers need Meta app review.
4. Point the app's redirect and webhook URLs at this site.
5. App ID and secret go in the server environment (names are added in Phase 4); never in the repository or in chat.

Until an account is connected and each feature is exercised against it, the page labels everything "not verified live".
