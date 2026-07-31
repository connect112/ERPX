# ERPX v1.0.0 — Release Checklist

Master checklist for cutting and shipping v1.0.0. Work top to bottom; do not skip
a gate. Companion docs live in `docs/release/`.

Release base commit: `925bfa0`  •  Target tag: `v1.0.0`

---

## 1. Pre-flight (code freeze)
- [ ] Working tree clean; on a release branch cut from `925bfa0`.
- [ ] Full backend suite green: `pytest` → **309 passing** (304 core + 5 perf), 0 failures.
- [ ] Alembic: `alembic heads` = single head `0038`; `alembic current` at head.
- [ ] No Critical/High findings open (see `docs/project-hardening-audit.md`, `docs/project-audit.md`).
- [ ] CI green on the release commit (backend tests+coverage+migration check; 4-app frontend build+test; dependency-vuln gate).

## 2. Version & metadata (`docs/release/VERSION_UPDATE.md`)
- [ ] `apps/api/app/main.py` → `version="1.0.0"`.
- [ ] `apps/{web,student-portal,trainer-portal,corporate-portal}/package.json` → `"version": "1.0.0"`.
- [ ] `CHANGELOG.md` finalized for 1.0.0 (date, contents).
- [ ] `RELEASE_NOTES.md` finalized.
- [ ] `LICENSE` present and correct.
- [ ] Commit: `chore(release): ERPX v1.0.0`.

## 3. Build & publish image (`docs/release/DEPLOYMENT.md` §1)
- [ ] CI builds from **repo-root context** with `apps/api/Dockerfile` and pushes `erpx-api:latest` + `:<sha>`.
- [ ] Image self-containment check passes: `docker run --rm --entrypoint python <image> -c "import app.main"`.
- [ ] Image scanned (no Critical/High OS/deps vulns) per policy.

## 4. Stage / pre-prod rehearsal
- [ ] Deploy to staging via Compose or a staging cluster.
- [ ] `alembic upgrade head` applied cleanly on staging.
- [ ] Full smoke test passes on staging (`docs/release/SMOKE_TEST.md`).
- [ ] Rollback rehearsed once on staging (`docs/release/ROLLBACK_PLAN.md`).

## 5. Secrets & environment (production)
- [ ] `erpx-secrets` populated: `JWT_SECRET_KEY` (≥32 chars, non-placeholder), `DATABASE_URL`, `REDIS_URL`, storage creds.
- [ ] `ENVIRONMENT=production`; TLS/HSTS terminated at ingress; CORS origins set to prod hosts.
- [ ] `docs/deployment/production-checklist.md` completed.

## 6. Production deploy (`docs/release/DEPLOYMENT.md` §2–3)
- [ ] Backup taken immediately before deploy (restore point verified).
- [ ] Migrations applied (one-shot Job/init) → `alembic current` = `0038`.
- [ ] Rollout image `1.0.0`; `kubectl rollout status` clean; all probes passing.

## 7. Post-deploy verification
- [ ] Production smoke test passes (`docs/release/SMOKE_TEST.md`), operator signed off.
- [ ] Observability live: metrics, traces, logs, error tracking.
- [ ] Celery worker + beat healthy; scheduled jobs firing.

## 8. Tag & announce (`docs/release/GIT_TAG_INSTRUCTIONS.md`)
- [ ] Annotated (preferably signed) tag `v1.0.0` created and pushed.
- [ ] GitHub Release published with notes.
- [ ] Stakeholders notified; support/on-call briefed; rollback plan linked.

## 9. Post-release (1.0.x backlog)
- [ ] Remove empty untracked `apps/api/{modules,packages}` stub dirs.
- [ ] Standardize list-response envelopes across endpoints.
- [ ] Monitor error rates/latency for 24–48h; hotfix as `v1.0.1` if needed.

---

### Go / No-Go sign-off

| Role | Name | Decision (GO/NO-GO) | Date |
|---|---|---|---|
| Release Manager | | | |
| Engineering Lead | | | |
| QA Lead | | | |
| Ops / SRE | | | |
