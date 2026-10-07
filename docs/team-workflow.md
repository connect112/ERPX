# Working on ERPX as a team

Two people (or more) can work on this project at the same time without overwriting each other, as long as everyone
follows the same few rules. This page is for a new developer starting from nothing.

## 1. Get the code and run it

1. Install: **Git**, **Docker Desktop**, **Node.js 20+**, **Python 3.12**, and (optional) the GitHub CLI `gh`.
2. Ask the repo owner to add your GitHub username as a collaborator, accept the invitation (email or
   github.com/notifications), then:
   ```bash
   git clone https://github.com/connect112/ERPX.git
   cd ERPX
   cp .env.example .env        # local settings only; never commit .env or paste real keys into it
   ```
3. Start the supporting services and the app (see `README.md` for the full list):
   ```bash
   docker compose up -d postgres redis minio
   cd apps/api && python -m venv .venv && .venv/Scripts/activate    # Windows; on Mac/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   alembic upgrade head                                            # creates your own local database tables
   uvicorn app.main:app --reload --port 8000
   ```
   In another terminal, the site you work on, for example the LMS student portal:
   ```bash
   cd apps/student-portal && npm install && npm run dev
   ```
4. Your database is **yours alone** (it lives in Docker on your laptop). Nothing you do locally touches the live site.

## 2. Who owns what

| Area | Where it lives |
|---|---|
| LMS student site (lms.pentrix.in) | `apps/student-portal` |
| LMS backend | `modules/lms`, `modules/courses`, `modules/batches`, `modules/live_classes`, `modules/students`, `modules/messaging` |
| Trainer / employee sites | `apps/trainer-portal`, `apps/employee-portal` |
| Admin site (erp.pentrix.in) | `apps/web` |
| Hackathons, exams, certificates, email templates | `modules/hackathons`, `modules/workshop_exams`, `modules/email_templates`, `apps/web/src/features/{hackathons,workshop-exams,email-templates}` |

Stay inside your own area. If a change needs a file in someone else's area (or a shared file such as
`apps/api/app/api/v1/router.py`, `apps/api/alembic/env.py`, `packages/`), tell the owner first and keep that change
small and separate.

## 3. The daily workflow (this is what prevents conflicts)

1. **Start from the latest master.**
   ```bash
   git checkout master && git pull
   git checkout -b yourname/short-description        # e.g. chethan/lms-schedule-fix
   ```
2. Work and commit on **your branch only**. Never commit directly to `master`, never edit someone else's branch.
3. Before opening a pull request, bring in anything new from `master` and re-run the checks:
   ```bash
   git fetch origin && git merge origin/master        # fix any conflict here, on your own branch
   ```
   - Backend: run the tests for the code you changed (`pytest tests/api/test_<area>.py`).
   - Frontend: `npx tsc -b`, `npx eslint src`, `npx vitest run` inside the app folder.
4. Push your branch and open a **pull request** into `master` (`gh pr create` or the GitHub website). Keep it small
   (one task). The owner reviews and merges.
5. After it is merged, go back to step 1 for the next task.

Small pull requests that merge quickly are the single best way to avoid conflicts.

## 4. Database migrations: the one thing that clashes

Migrations live in `apps/api/alembic/versions/` and are numbered in order (`0063_...`, `0064_...`). Two people adding
"the next number" at the same time collide.

- Pull `master` right before you create a migration and use **the highest existing number + 1**.
- Say in the team chat that you are taking that number.
- If your pull request is merged second and the number is already taken, renumber yours (change the file name,
  `revision`, and `down_revision`) before merging.
- Never edit a migration that is already on `master`; add a new one.

## 5. Going live

Only the repo owner deploys to the live servers (erp.pentrix.in, lms.pentrix.in). Developers do **not** merge to
`master` or deploy on their own. Your work reaches students after the owner merges and deploys it.

## 6. Using Claude Code on your laptop

- Each person's Claude works on their own laptop's copy of the code, so two sessions never edit the same files.
- Claude does not remember other people's sessions. Everything it needs to know about how we work is in this file
  and in `CLAUDE.md`; ask it to read both at the start of a session.
- Tell Claude which branch you are on and which area you own. Do not paste API keys or passwords into chats; keep
  secrets in your local `.env` only.
