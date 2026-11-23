# ERPX: start here (for a fresh Claude Code Local session)

Written 2026-11-03 at the end of the Claude Code Cloud sessions, by the Cloud session
(`https://claude.ai/code/session_01U5P4cF39213YhoF5YCkj3w`). The Cloud container is ephemeral; everything worth keeping is
in GitHub (`connect112/ERPX`) and in the documents listed here. Nothing in this file is a secret.

## 0. Rules for this session (read first)

1. Read `CLAUDE.md` and `docs/team-workflow.md` in the repository. They are binding.
2. **Never work on `master`.** New branch from the latest `origin/master`, named `<developer>/<task>`.
3. **Do not merge any pull request, do not deploy, do not touch AWS production, do not enable live Cashfree.**
   Merging and deploying belong to the owner (Srujan) only. See `ERPX_LOCAL_MIGRATION_GUIDE.md` section 10 for the full list.
4. **Never print, commit or ask for secrets** (`.env`, Cashfree App ID / Secret Key, webhook signatures, tokens, passwords).
5. **Do not assume the original computer matches GitHub.** Inspect it read-only first (migration guide, section 2). Do not
   overwrite local databases, Docker volumes, `.env` files or uncommitted work.
6. Do not disable or skip tests, and do not weaken security gates, to make CI green.
7. **No production deployment is authorized** (neither PR #163, #164 nor #162). Do not merge #163 or #164 or any PR
   automatically; do not enable live Cashfree (`CASHFREE_ENV=production` / `CASHFREE_ALLOW_PRODUCTION=true`); do not modify AWS
   production resources; do not delete Docker volumes, containers, images or databases; do not mix CI fixes into the Cashfree PR
   without a deliberate decision by the owner; do not add dependencies upgrades to either PR.

## 1. Exact GitHub state when this was written (verify it again; do not trust it blindly)

| Item | Ref | State |
|---|---|---|
| `master` | `86e4a86334eb60015f713c059bf406bdb2ca015c` | The owner stated this is the production commit on 2026-11-01. It had not moved at 2026-11-03 14:3x UTC. |
| PR #163 Cashfree sandbox acceptance | branch `claude/cashfree-sandbox-readiness`, head `d96b97606c9bbf0d2eedc1414844cbc4daa8531d` | **Open**, not draft, 26 commits, `mergeable_state: blocked`. Needs independent review and the owner's merge. Not deployed. |
| PR #164 CI repair | branch `claude/ci-repair-tests-and-minio`, head `827385cac01d7bcd825e7b94bd3a99e365ca471f` | **Open**, 2 commits. Last CI run #11: backend `2 failed, 2204 passed, 6 skipped`; pip-audit gate and the four npm-audit gates red. Not deployed. |
| PR #162 Onboarding / Onboarding Settings tabs | branch `claude/onboarding-settings-tab`, head `62d661125f9b23b85f68e6e3dae7f7bbb97a3659` | **Open, draft**, never reviewed or merged. Merges cleanly with #163 and #164. |
| PR #158 / #159 | `srujan/cloud-handoff` / `claude/pensive-wozniak-81byk7` | Open drafts, superseded by merged #160 (kept open on purpose). |
| Merged earlier | #157 security updates, #160 bulk download, #161 internship onboarding | On `master`. |
| This handoff | branch `claude/handoff-docs` | Documentation only (see the handoff PR). |

**Known integration problem:** #163 and #164 both edit `.github/workflows/ci.yml` next to each other and **conflict** (one
hunk: the Celery compatibility step vs the new MinIO steps). The PR #164 description says they "merge cleanly"; that is true for
the trigger and `PYTHONPATH` lines only, and is **wrong overall**. Resolution: keep both. See `ERPX_CI_REPAIR_HANDOFF.md` section 7.

## 2. The documents

| File | Read it for |
|---|---|
| `ERPX_COMPLETE_DEVELOPMENT_HISTORY.md` | The whole story, chronologically, with commit hashes and what is verified vs reported. |
| `ERPX_CASHFREE_TECHNICAL_HANDOFF.md` | How the Cashfree integration works (files, functions), the sandbox test record, limits, production restrictions. |
| `ERPX_CI_REPAIR_HANDOFF.md` | The CI investigation, PR #164, run numbers, every remaining failure and the proposed fixes. |
| `ERPX_LOCAL_MIGRATION_GUIDE.md` | How to move onto the original computer safely (read-only inspection first). |
| In PR #163's branch: `docs/CASHFREE_SANDBOX.md`, `docs/CASHFREE_REVIEW_HANDOFF.md` | The acceptance record and the reviewer/owner handoff (not on `master` yet; `git show origin/claude/cashfree-sandbox-readiness:docs/...`). |
| On `master`: `docs/CLOUD_HANDOFF.md`, `docs/internship-onboarding.md`, `docs/INTERN_ONBOARDING_PROGRESS.md`, `docs/operations/*`, `ops/release-internship-onboarding/CHECKLIST.md` | Earlier architecture, AWS, deployment and rollback knowledge. |

## 3. Continuation plan (do in this order; each step ends with a report to the owner)

**A. Read-only environment inspection.** *Prerequisite:* none. *Do:* `ERPX_LOCAL_MIGRATION_GUIDE.md` sections 2 and 4 (Git state, untracked/ignored files, stashes, branches, `.env` variable *names*, Docker containers/volumes/networks, database names and `alembic_version`). *Risk:* printing secrets or touching state; use only the listed commands. *Done when:* the owner has a written report (branch, local-only commits, uncommitted files, stashes, Docker/DB inventory, port/volume collisions) and says go.

**B. Safely synchronize Git metadata.** *Prerequisite:* A approved, backup made (guide section 3: copy + `git bundle`, verified). *Do:* `git fetch --no-tags origin`; compare history (guide section 5). Expect `master` = `86e4a86…` (verify). *Risk:* local-only commits being overwritten; never `pull`, `reset` or `rebase` the old checkout. *Done when:* the ahead/behind table per local branch is shown and any local-only commits are listed.

**C. Create an isolated workspace for PR #164.** *Prerequisite:* B. *Do:* separate clone/worktrees as in guide section 6: `erpx-pr164` (branch `claude/ci-repair-tests-and-minio`), `erpx-pr163`, `erpx-handoff`; a throwaway PostgreSQL 16 + Redis 7 + pinned MinIO with a new Compose project name and ports; its own `.env`. *Risk:* mixing branches or reusing the old stack's data. *Done when:* `git worktree list` shows the separate directories, `git branch --show-current` is right in each, and the throwaway services run beside (not instead of) the old ones.

**D. Reproduce and fix the remaining backend CI problem (PR #164 only).** *Prerequisite:* C. *Do:* `ERPX_CI_REPAIR_HANDOFF.md` sections 6 and 10: print `pg_dump`/`pg_restore`/`psql` versions and the server version, reproduce the two `TestCompressedBackupRestore` failures with client 16/17/18 against a 16 server; then propose (owner approves) a CI client pin or a diagnostic step. Run only the relevant tests, not the 15 to 40 minute suite, until the end. *Risk:* "fixing" it by skipping or by changing application restore behaviour without approval. *Done when:* CI on #164 shows 0 failed backend tests (the audit gates will still be red until E).

**E. Investigate the npm and pip advisories separately.** *Prerequisite:* C; one branch/PR per concern, from the latest `master`. *Do:* `ERPX_CI_REPAIR_HANDOFF.md` section 8: re-run `npm audit --json` per app and `pip-audit`; candidates: `happy-dom` 21.0.4 + `@tiptap/html` 3.32.2 (in range); `vite` 6.4.5 + `vitest` 4.1.12 together (Node 20 compatible; **not** vitest 5/vite 8 which need Node 22/20.19); `pypdf` 6.21.4 (patch); `zod` 4 is a large migration or an owner-approved, expiring exception. *Risk:* `npm audit fix --force`; breaking 175 files; lockfile churn. *Done when:* each advisory has an owner-approved outcome and the gates are green without being weakened.

**F. Obtain an independent review of Cashfree PR #163.** *Prerequisite:* none technical; GitHub requires a reviewer other than the author. *Do:* give the reviewer `docs/CASHFREE_REVIEW_HANDOFF.md` (on the #163 branch) and `ERPX_CASHFREE_TECHNICAL_HANDOFF.md`; resolve the `ci.yml` conflict with #164 when the second merges (CI document, section 7). *Risk:* self-approval; merging with red CI unexplained. *Done when:* a recorded independent approval and the owner's decision on CI.

**G. Complete release prerequisites without deploying.** *Prerequisite:* F. *Do:* only prepare: `ERPX_CASHFREE_TECHNICAL_HANDOFF.md` section 9 (compose pass-through as a separate change, secrets, webhook, whitelist, MinIO image preservation, a restore rehearsal for the `pg_restore` question in the CI document section 6). *Risk:* anything touching production or live Cashfree. *Done when:* the owner has a written checklist with every item marked owner-done or not; nothing deployed.

**H. Offer-letter + onboarding-link email (future).** *Prerequisite:* new branch from the latest `origin/master` (for example `<developer>/offer-letter-onboarding-link`), separate from every PR above, and a written design agreed with the owner first (none exists). Starting points in the code (verified): offer letters in `modules/our_internships/letters.py`, `letter_tasks.py`, `letter_models.py` (versioned PDF letters, approval, release, Celery email, delivery history; email through the Email Studio template `internship_offer_letter`); the student's personal onboarding link in `modules/internship_onboarding/service.py` (`issue_link`, `link_for`; only a SHA-256 of the token is stored; links rotate on every send). *Risk:* the owner paused Email Studio changes on 2026-11-01; touching templates/rendering needs explicit approval; raw tokens must exist only in memory when the email is built. *Done when:* design approved, tests added, browser check as a plain Administrator, PR opened as draft.

## 4. The immediate next task

Start with the read-only inspection. Do not run `git pull`, `git checkout`, `git reset`, `docker compose up/down`, `alembic`, or
any test suite on the original computer until the inspection report has been shown to the owner.

## 5. The first instruction to give Claude Code Local

Paste this as the first message (it contains no secrets):

> Read `CLAUDE.md`, `docs/team-workflow.md` and, from GitHub branch `claude/handoff-docs` of connect112/ERPX, the five files in
> `docs/handoff/` (start with `ERPX_LOCAL_START_HERE.md`; use `git fetch origin claude/handoff-docs` and
> `git show origin/claude/handoff-docs:docs/handoff/ERPX_LOCAL_START_HERE.md`, without switching branches).
> Then do ONLY the read-only inspection described in `ERPX_LOCAL_MIGRATION_GUIDE.md` sections 2 to 4 on this computer: Git state, uncommitted and
> untracked files, stashes, local branches vs GitHub, Docker containers/volumes/networks, database names, and which `.env`
> files exist (names only, never their contents). Change nothing, run nothing that writes, do not merge, deploy, or touch
> production or Cashfree. Report what you found and wait for my decision before any other step.

## 6. What must not be repeated

- Do not re-run Cashfree sandbox payments or create more synthetic students: manual sandbox testing was closed by the owner on
  2026-11-03 (Test 10 stays "partially verified" and USER_DROPPED stays "not observed"; documented, accepted).
- Do not re-derive the CI failures from scratch: they are fully classified in `ERPX_CI_REPAIR_HANDOFF.md`.
- Do not look for `main` or `develop`: the repository's only long-lived branch is `master`.
- Do not try to download GitHub Actions logs through `curl` from a restricted network; use the log tool with a large `tail_lines`
  saved to a file and filter it (the Cloud proxy blocked the log blob host).
- Do not push to `claude/cashfree-sandbox-readiness` or `claude/ci-repair-tests-and-minio` unless the owner decides to continue
  those PRs deliberately; mixing CI fixes into the Cashfree PR needs a deliberate decision.
