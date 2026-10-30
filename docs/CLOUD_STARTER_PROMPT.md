# Starter prompt for a new Claude Code Cloud session

Copy everything inside the block into the first message of the new session.

```text
You are continuing development of ERPX (repo connect112/ERPX) for the owner, Srujan. Start by reading, in this order:
1. CLAUDE.md and docs/team-workflow.md (rules: never work on master, branch as <developer>/<task>, no deploys, no merges without the owner, no secrets).
2. docs/CLOUD_HANDOFF.md (architecture, AWS, deployment scripts, what is verified, security status, outstanding tasks, payment requirements, local setup).
3. docs/operations/2026-10-30-rollout-plan.md only if you touch deployment or backups.

State: the Stage 4 and 5 release (backup safeguards, monitoring, Storage Manager, migration 0096, security dependency updates) is deployed; production
is at 0096 (handoff section 5 lists what is still open). Universal Bulk Download is implemented in PR #159 (migration 0097, handoff section 12) and
awaits owner review and deploy. Do not redo the completed investigations (S3 archive and cleanup, disk recovery, dependency audit, migration rollback
test, CI diagnosis, bulk-download release review); they are summarised there.

Rules for this session:
- You have no AWS or production access. Prepare code, tests, scripts and runbooks; the owner runs production steps and approves each one.
- Open draft PRs, one per phase, with what changed and how it was verified. Do not merge or deploy. Do not weaken security or CI gates.
- Do not add secrets, keys or passwords to the repo, logs or replies. Payment credentials must be stored encrypted and be write-only.

Task: build the universal, admin-configurable payment system described in section 10 of docs/CLOUD_HANDOFF.md, Cashfree first, with a provider
interface that makes Razorpay and other providers an adapter, not a rewrite. First ask the owner to confirm scope (which modules take payments first,
INR only or multi-currency, webhook URL, refunds in scope) and then propose a phased plan before writing code. Keep the first PR to the provider
abstraction, data model migration (next free number on master: after 0096, or after 0097 once #159 is merged) and Cashfree adapter with
mocked-sandbox tests.
```
