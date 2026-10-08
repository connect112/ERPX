# ERPX: rules for Claude Code sessions

Read `docs/team-workflow.md` first. Summary of what matters in every session:

- Several developers work on this repo at once. **Never work on `master`**: start from the latest `master`
  (`git fetch origin` + `git merge --ff-only origin/master`) on a new branch named `<developer>/<task>`.
- **Stay in the developer's area** (see the table in `docs/team-workflow.md`). Do not edit other areas or shared files
  (`apps/api/app/api/v1/router.py`, `apps/api/alembic/env.py`, `packages/`) without saying so and keeping it a small,
  separate change.
- **Migrations** are hand-written, numbered in order under `apps/api/alembic/versions/`. Check the highest number on
  the latest `master` before adding one, use the next, and never edit one that is already merged.
- **Verify before a pull request**: backend tests for the code you changed, and for a frontend app `npx tsc -b`,
  `npx eslint src`, `npx vitest run`. Check UI changes in the browser as a plain Administrator (not Super Admin).
- **Do not deploy** and do not merge your own pull request unless the repo owner (Srujan) has said to. The live
  servers are managed by the owner only.
- **Secrets**: never commit `.env`, API keys, passwords or tokens; never print them in replies or logs; never ask the
  user to paste a secret into chat.
- Commit messages end with the co-author line the tool provides; pull request descriptions list what changed and how
  it was verified.
