# ERPX: moving development to the original computer (safe procedure)

For Claude Code Local, working with the owner. **This guide was written without access to the original computer. It makes no
assumption that it matches GitHub, that it is a Mac, Windows or Linux machine, or that its Docker/database state is healthy. Nothing in
this guide was executed there.** Every command below is either read-only or is marked WRITES and requires the owner's explicit OK.
Never print secret values: when a file may contain secrets, list **names only**.

## 0. Ground rules

1. Do the sections in order. Stop and report after sections 2 to 4 (inspection) and wait for the owner's decision.
2. Do not run on the original checkout: `git pull`, `git checkout <other branch>`, `git reset`, `git clean`, `git stash` (even `stash` hides work), `git rebase`, `git merge`, `git gc`, `docker compose up/down/build`, `docker system prune`, `docker volume rm`, `alembic upgrade/downgrade/stamp`, `npm install` / `pip install` (they change the working tree/venv), or any test suite.
3. The original checkout, its databases and Docker volumes are **evidence of older work**. They may hold uncommitted code and data that exist nowhere else.
4. All new work happens in **new** directories (worktrees or fresh clones), with **new** Compose project names, ports, containers and databases. Never reuse the old stack's database or volumes for tests.
5. Secrets (`.env`, Cashfree App ID/Secret Key, webhook signatures, database passwords, AWS credentials, SSH signing keys, tokens) stay on that machine, are never committed, never pasted into chat, and are never copied into the repository.

## 1. What the Cloud session knows about the original machine (and does not)

Known from the conversation (OWNER): there is an "original development computer" with an older codebase, local databases, Docker volumes, configuration and possibly uncommitted work; before the Cloud move the owner used local Claude Code. A separate MacBook Pro M3 Pro holds the sandbox staging stack at `~/erpx-cashfree-staging/ops/staging-cashfree` (never `~/erpx-cf-staging`), with its own Docker containers and networks (including an unrelated project with "RASKGF" containers) and git-ignored evidence directories. **UNVERIFIED:** whether the "original computer" is that Mac or another machine (`docs/team-workflow.md` has Windows instructions, e.g. `.venv/Scripts/activate`).
Unknown: the local branch names, any local commits not on GitHub, uncommitted files, local migration revision, which Docker volumes hold data.

## 2. Read-only inspection of the Git checkout (do this first)

Run from the original checkout; every command only reads.

```bash
pwd; git rev-parse --show-toplevel
git status --porcelain=v1 --branch --untracked-files=all       # modified, staged, untracked files
git status --ignored --short | head -100                        # ignored files (often .env, evidence dirs, caches)
git stash list                                                  # hidden work
git branch -vv --all                                            # local + remote-tracking branches and upstreams
git remote -v                                                   # must point to github.com/connect112/ERPX (or a fork)
git log --oneline --decorate -n 25                              # where HEAD is
git worktree list                                               # existing worktrees
git config --get-regexp '^(user\.|gpg\.|commit\.gpgsign|core\.autocrlf|core\.hooksPath)'   # identity + signing setup (names/values of config are not secrets, but do not print key material)
git submodule status 2>/dev/null
git diff --stat; git diff --cached --stat                       # size of uncommitted changes
```
Record: current branch, how far it is from `origin/master` (section 5), every untracked/ignored file you did not expect, stashes, and whether commits are SSH-signed (the PR branches on GitHub are SSH-signed; the owner checks "Verified").
**Important:** these listings come from the *last fetch* the old checkout made. Do not conclude anything about GitHub until section 5.

## 3. Preserve everything before any write (WRITES to a backup location only; ask the owner)

```bash
# a full copy of the working directory, including .git, untracked and ignored files, OUTSIDE the repository
cp -a <repo> <backup_dir>/erpx-original-$(date +%Y%m%d-%H%M)        # Linux/macOS; use robocopy /E on Windows
# a portable copy of all commits, refs and stashes
git -C <repo> bundle create <backup_dir>/erpx-original.bundle --all
git -C <repo> stash list >/dev/null                                   # (bundle --all includes refs/stash)
```
- Verify: `git bundle verify <backup_dir>/erpx-original.bundle`; compare file counts and sizes (`find <repo> -type f | wc -l`).
- Store backups where the owner decides; if they contain `.env` files, keep them in encrypted storage. Never upload a backup that contains secrets to GitHub or to a chat.
- Disk space: check before copying (`df -h`); node_modules and Docker data can be large (the copy may exclude `node_modules`, which is reproducible; say so in the report).

## 4. Read-only inspection of configuration, Docker and databases

### 4.1 Environment files (names only)
```bash
find <repo> -maxdepth 3 \( -name '.env' -o -name '.env.*' -o -name 'staging.env' -o -name '*.pem' -o -name '*.key' \) -not -path '*/node_modules/*' -not -path '*/.git/*'
# for each .env-style file: list VARIABLE NAMES only (never values)
grep -E '^[A-Za-z_][A-Za-z0-9_]*=' <file> | cut -d= -f1 | sort
```
Compare names with `.env.example` (`diff <(grep -E '^[A-Za-z_]' .env.example | cut -d= -f1 | sort) <(…same for the real file…)`) to see which settings are missing or extra. The Cashfree variables are `CASHFREE_ENABLED`, `CASHFREE_ENV`, `CASHFREE_ALLOW_PRODUCTION`, `CASHFREE_APP_ID`, `CASHFREE_SECRET_KEY`, `CASHFREE_API_VERSION`, `CASHFREE_ORDER_MINUTES`, `CASHFREE_WEBHOOK_MAX_AGE_HOURS`: record **whether they are set**, never their values, and never run anything with `CASHFREE_ENV=production`.
Do **not** run `docker compose config` or `printenv` (they print resolved secrets). Use `docker compose config --services` (names only) if needed.

### 4.2 Docker (read-only)
```bash
docker version --format '{{.Server.Version}}' 2>&1 | head -1
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker volume ls
docker network ls
docker network inspect <network> --format '{{.Name}} {{range .IPAM.Config}}{{.Subnet}}{{end}}'     # subnets, to avoid collisions
docker volume inspect <volume> --format '{{.Name}} {{.Mountpoint}}'
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}'
docker compose ls                                                                                   # which Compose projects exist
```
Note, for the report: which containers are PostgreSQL / Redis / MinIO / Mailpit, their images (the MinIO image matters: `minio/minio` can no longer be pulled, so **do not delete or `prune` images and do not `docker compose pull`**; the local image may be the only copy), volume names (for example `erpx_minio_data`, `erpx_postgres_data` style names; confirm the real ones), and ports in use (5432, 6379, 9000, 8000, 3000 and the staging ports) so new stacks avoid them.

### 4.3 Databases (read-only; do not connect a migrating application to them)
```bash
docker exec <postgres container> psql -U <user> -Atc "select datname from pg_database where not datistemplate"
docker exec <postgres container> psql -U <user> -d <db> -Atc "select version_num from alembic_version"
docker exec <postgres container> psql -U <user> -d <db> -Atc "select count(*) from information_schema.tables where table_schema='public'"
```
(Use the credentials already in that container's environment through `docker exec`; do not paste passwords.) Compare the revision with the repository: `master` head is `0100_internship_financial_documents`; production was at `0097` before PR #161 and the owner reports the release of `86e4a86`. **A local database behind `0100` must not be upgraded in place.** Upgrade a *copy*: `pg_dump -Fc <db> > <backup>` first (checked with `pg_restore --list`), restore into a new database/volume, and run `alembic upgrade head` there.

## 5. Compare local history with GitHub (after the backup in section 3)

```bash
git fetch --no-tags origin            # WRITES only remote-tracking refs and objects; needs the owner's OK after the backup
git rev-parse origin/master           # expect 86e4a86334eb60015f713c059bf406bdb2ca015c (verify; master may have moved)
git merge-base HEAD origin/master
git log --oneline --left-right --cherry-pick HEAD...origin/master | head -50
git log --oneline origin/master..HEAD                    # local-only commits (these exist nowhere else!)
git cherry -v origin/master HEAD                         # which local commits are not upstream even if re-created
for b in $(git for-each-ref --format='%(refname:short)' refs/heads); do echo "$b: ahead $(git rev-list --count origin/master..$b) behind $(git rev-list --count $b..origin/master)"; done
```
Interpretation: *behind only* → nothing to rescue, just start new worktrees; *ahead* → local-only commits: keep them (they are in the bundle), tell the owner, and do not rebase/force anything. Pushing them anywhere is outward-facing: only with the owner's approval and under a new, clearly named backup branch.

## 6. Create isolated checkouts for the pull requests (WRITES new directories only)

Keep the old checkout untouched and untouched means *not even switching its branch*. From a **separate clone** (or from the old repo using `git worktree add`, which only adds a new directory and a `.git/worktrees` entry; a separate clone is cleaner and recommended):

```bash
mkdir -p ~/erpx-work && cd ~/erpx-work
git clone https://github.com/connect112/ERPX.git erpx-main      # reference clone on master (read-only use)
cd erpx-main
git worktree add ../erpx-pr164 -b claude/ci-repair-tests-and-minio origin/claude/ci-repair-tests-and-minio
git worktree add ../erpx-pr163 -b claude/cashfree-sandbox-readiness origin/claude/cashfree-sandbox-readiness
git worktree add ../erpx-handoff -b claude/handoff-docs origin/claude/handoff-docs     # docs only
git worktree list
```
Rules for the worktrees:
- One PR per directory; never commit PR #164 work in the #163 directory or the reverse. Check `git branch --show-current` before every commit.
- New feature work (for example the offer-letter email) → a new branch from the latest `origin/master` in a fourth directory: `git worktree add ../erpx-offer-email -b <developer>/offer-letter-onboarding-email origin/master`.
- Each worktree gets its **own** `.env` copied by hand from a template (`cp .env.example .env`, then fill local values yourself). `.env` is git-ignored; confirm with `git check-ignore -v .env`.
- Use a different Compose project name and different host ports from the old stack (`COMPOSE_PROJECT_NAME=erpx_pr164`, new ports, new volume names) so nothing can attach to the old volumes. Never use the old stack's database for tests: create a throwaway PostgreSQL 16 / Redis 7 / pinned MinIO (see the CI document).
- Install toolchains per worktree: Python 3.12 virtualenv (`apps/api`), Node 20+ (`apps/web` etc.). The CI uses Python 3.12 and Node 20.

## 7. Configuration that must remain local (never committed, never moved to GitHub or chat)

`.env` and every `.env.*` except `.env.example`; Cashfree App ID / Secret Key and webhook signing material; database and Redis passwords; MinIO keys; SMTP credentials; `JWT_SECRET_KEY`; `SEED_SUPERADMIN_*` values; AWS profiles and keys (`~/.aws`); the SSH key used to sign commits; `ops/staging-cashfree/staging.env`, `ops/staging-cashfree/evidence/`, gateway logs and the tunnel configuration (all git-ignored on the staging Mac); local database dumps and Docker volumes; any backup bundle that contains them.

## 8. Facts you need about the repository workflow

- Binding: `CLAUDE.md` and `docs/team-workflow.md` (branch `<developer>/<task>` from the latest `master`; stay in your area; migrations hand-written, numbered, never edit a merged one; verify before a PR; do not deploy; do not merge your own PR unless the owner says; secrets rules; commit trailers).
- The repository's only long-lived branch is `master`; production is `86e4a86` per the owner. Branch protection requires an independent review (the PR author `connect112` cannot approve their own PR).
- Commits on the PR branches are SSH-signed. Configure the same signing in the new clones if the owner wants "Verified" badges (do not copy private keys around; use the machine's existing key).
- Tests: backend `pytest.ini` has `pythonpath = apps/api .`; Alembic needs the repository root on `PYTHONPATH`. Frontend per app: `npx tsc -b`, `npx eslint src`, `npx vitest run`.
- Docker/Compose: `docker-compose.yml` (dev) and `docker-compose.prod.yml` (production) exist; **never change or run the production one**.

## 9. Order of operations and stop conditions

1. Inspect Git (section 2) → inspect env names, Docker, databases (section 4) → **report to the owner and wait**.
2. After approval: back up (section 3) → fetch (section 5) → report the comparison and wait.
3. After approval: create the worktrees (section 6); start work from the "Exact next steps" in `ERPX_LOCAL_START_HERE.md`.
Stop immediately and ask if: any command would modify the original checkout, a database or a volume; secrets would be displayed; local commits exist that GitHub lacks; a migration revision differs; a port or volume name collides; anything touches production or Cashfree live.

## 10. Never

Merge #162/#163/#164 or any PR; deploy; run AWS commands against production; enable live Cashfree (`CASHFREE_ENV=production` / `CASHFREE_ALLOW_PRODUCTION=true`); delete Docker volumes, containers, networks, images or databases of the old setup; run `./staging.sh destroy`, `down -v` or `recreate-network` on a staging stack that holds evidence; paste secrets; force-push; rewrite published history; skip tests or weaken gates.
