# Single-host AWS deploy (pentrix.in + erp.pentrix.in + lms.pentrix.in + staff.pentrix.in)

A deliberately small deployment target: one EC2 instance running
Pentrix-share, ERPX's admin frontend, ERPX's student portal (LMS), and
ERPX's employee portal behind one Caddy reverse proxy, sharing one
Postgres and one Redis container to fit a free-tier-sized box. This is
**not** the same deployment path as
`infrastructure/terraform/` + `infrastructure/kubernetes/` (a real AWS/EKS
production setup) — that path stays as documented, untouched, for when
this project actually needs it. This directory is the pragmatic
hobby/demo-scale alternative.

It lives in the ERPX repo (not a third, separate repo) because it's the
shared infrastructure both apps depend on — Postgres, Redis, and the
reverse proxy aren't owned by either app individually.

## Layout on the instance

```
/opt/infra/                  <- this directory, copied from the ERPX clone
  docker-compose.yml           postgres, redis, caddy
  postgres-init/                runs once on first Postgres boot
  Caddyfile
  .env                          shared secrets (never committed)
  deploy.sh                     pulls + rebuilds both apps
/opt/erpx/                    <- git clone of this repo
  docker-compose.prod.yml       api, celery_worker, celery_beat, web,
                                 student_portal, employee_portal, minio
  .env                          ERPX-specific secrets
/opt/pentrix/                  <- git clone of the Pentrix-share repo
  docker-compose.prod.yml       migrate, backend, frontend
  .env                          Pentrix-specific secrets
```

All three compose projects join one external Docker network, `webnet`
(created by `docker-compose.yml` here) — that's how the app containers
reach the shared `postgres`/`redis` containers by name, and how Caddy
reaches each app's own container by name.

## Why one shared Postgres/Redis instead of one per app

Both apps' own local-dev compose files run their own Postgres + Redis.
Free-tier RAM (1 GB) doesn't comfortably fit four database-adjacent
processes. `postgres-init/01-create-databases.sh` creates two separate
databases and two separate users (`erpx`/`pentrix`) in the one Postgres
instance on first boot — each app still has its own fully isolated
database and credentials, just sharing the one Postgres process. Redis
separates the two apps by DB index instead (ERPX already does this
internally for its own broker/backend/cache; Pentrix-share gets the next
two free indexes).

## Updating either app from here

```
ssh-less — via AWS Systems Manager:
aws ssm send-command --instance-ids <id> --document-name "AWS-RunShellScript" \
  --parameters 'commands=["/opt/infra/deploy.sh"]'
```

`deploy.sh` does `git pull` in both `/opt/erpx` and `/opt/pentrix`, then
`docker compose -f docker-compose.prod.yml up -d --build` in each — a
single command deploys whatever is newest on each repo's default branch.

## One-time content seeding (fresh database only)

A brand-new Postgres has no rows, so Pentrix-share's blog is empty until
`backend/scripts/import_blog_posts.py` (Markdown-authored posts under the
Pentrix-share repo's own `content/blog/`) is run once against it. Not
part of `deploy.sh` because it's an idempotent *content* import, not a
schema migration — re-run it any time a Markdown file changes; it
upserts by slug. The Pentrix-share backend image's build context is
`./backend` only, so `content/` isn't baked into it — mount the full
repo checkout instead:

```
PW=$(grep '^PENTRIX_DB_PASSWORD=' /opt/pentrix/.env | cut -d= -f2)
docker run --rm --network webnet -v /opt/pentrix:/repo -w /repo/backend \
  --env-file /opt/pentrix/.env -e PENTRIX_ENV=production \
  -e PENTRIX_DATABASE_URL="postgresql://pentrix:${PW}@postgres:5432/pentrix" \
  pentrix-prod-backend python scripts/import_blog_posts.py
```
