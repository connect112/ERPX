# ERPX CI repair: investigation, PR #164, and what is left

Written 2026-11-03. Provenance tags: GIT (verified in the repository), GH (verified from the GitHub API/CI), CLOUD (reproduced in the
Cloud container; the container is gone), OWNER, UNVERIFIED. Re-verify CI states before relying on them.

## 1. Status at a glance (GH, 2026-11-03 about 14:40 UTC)

| Item | Value |
|---|---|
| PR #164 | `claude/ci-repair-tests-and-minio`, head `827385cac01d7bcd825e7b94bd3a99e365ca471f`, 2 commits, **open**, base `master` `86e4a86`, `mergeable_state: blocked` (review/branch protection), 71 additions / 8 deletions in 6 files. Not deployed. |
| Last completed CI run on #164 | **#11**, run id `41649604936`, URL https://github.com/connect112/ERPX/actions/runs/41649604936, conclusion **failure** |
| Backend tests in run #11 | **2 failed, 2204 passed, 6 skipped** (1552.71 s = 25m52s) |
| Remaining backend failures | `tests/integration/test_restore_backup_integration.py::TestCompressedBackupRestore::test_compressed_archive_restores_into_an_empty_database` and `::test_compressed_archive_replaces_an_existing_schema_when_asked` (both `assert <ExitCode.RESTORE_FAILED: 6> == <ExitCode.SUCCESS: 0>`) |
| pip-audit gate (now runs even after test failure) | **FAIL**: 13 findings in 4 packages; 7 are HIGH (all `pypdf` 6.21.2) |
| npm-audit gate (4 jobs: web, student-portal, trainer-portal, corporate-portal) | **FAIL** in all four (build, type check and frontend tests pass first) |
| PR #163 CI | Last inspected run #8 (`41635464455`, head `b9852ff`): backend test step failed (see 3.3), gates failed. Run #9 (head `d96b976`) was never inspected. #163 has not been re-run with #164's fixes. |

## 2. Why GitHub Actions never ran for `master` (GIT/GH)

`.github/workflows/ci.yml` triggered on `push` and `pull_request` for branches `[main, develop]` only. The repository's only
long-lived branch is `master`, so no pull request into `master` ever ran the backend tests, frontend builds/tests or dependency scans.
`docker-publish.yml` publishes images only through a `workflow_run` of "ERPX CI" on branch `main`, so adding `master` does **not**
publish images. Fix (identical in #163 and #164, and on the owner's branch `srujan/ci-run-on-master`): `branches: [main, master, develop]`.

## 3. Run-by-run record

### 3.1 Earlier runs (UNVERIFIED details; from the owner's earlier branches as seen in the previous Cloud session)
Runs #2 to #6 (ids `41011257023`, `41034142789`, `38704157570`, `38711637062`, `38713725840`) were earlier failures on the owner's CI branches. The only item re-confirmed in this engagement: run `41011257023` recorded the missing-`PYTHONPATH` migration failure (quoted in commit `b9852ff`). The owner's `docs/CLOUD_HANDOFF.md` §7 also records: "backend job has no MinIO service and no `pg_dump`, so storage/backup tests fail there… CI never gated deployment."

### 3.2 Run #7: `41635227168`, PR #163, head `f386fca` (trigger fix)
First run ever for a `master` pull request. Backend: install OK; **Celery/Kombu/redis-py compatibility step OK** (real Redis service); **"Run migrations" FAILED** with `ModuleNotFoundError: No module named 'modules'` (`alembic/env.py` imports the top-level `modules` package; the step runs from `apps/api`, so the repository root was not on `PYTHONPATH`); tests and pip-audit skipped. Frontend ×4: install/build/tests OK; npm-audit gate FAILED.

### 3.3 Run #8: `41635464455`, PR #163, head `b9852ff` (PYTHONPATH fix)
`PYTHONPATH: ${{ github.workspace }}` added to the migration step only. Migrations OK; backend test step FAILED after about 32 minutes (`12:25:37Z` to `12:57:40Z`); pip-audit steps skipped (they follow the failed step); frontend ×4 gate FAILED. **The per-test list for this CI run was not readable** (log access, section 9). The identical command was run in the Cloud on a freshly migrated database (no MinIO, no roles): **65 failed, 14 errors, 2197 passed, 6 skipped in 2239 s**, i.e. **79 problems**, all classified in section 4. The CI step duration is consistent with that (storage timeouts dominate).

### 3.4 Run #10: `41644827815`, PR #164, head `64a04af` (MinIO + fixtures + migration test)
MinIO start step OK in about 6 s (live and ready checks passed), bucket step OK, migrations OK. Backend tests: **3 failed, 2203 passed, 6 skipped in 996.07 s (16m36s)**:
- `tests/api/test_hackathon_participants.py::test_a_team_is_joined_only_with_its_code_which_only_its_members_and_staff_can_see`: `AssertionError: assert ['F4SDXS', 'GEVNDN'] == ['GEVNDN', 'F4SDXS']`
- the two restore tests above.
pip-audit scan ran for the first time (after the `!cancelled()` change) and the gate failed: 7 HIGH.

### 3.5 Run #11: `41649604936`, PR #164, head `827385c` (team-order test fixed)
Backend tests **2 failed, 2204 passed, 6 skipped in 1552.71 s**. The two failures are the restore tests only. pip-audit gate failed (same 13 findings, same 7 HIGH). npm gates failed ×4.

Result of the repair: 79 problems → 2 (plus the two audit gates). Both `test_integrations` and `test_storage_public_urls`, the two tests that need a real MinIO, **passed** in CI.

## 4. Classification of the original 79 problems (CLOUD reproduction; each group proven as stated)

| Group | Count | Cause | Class | Proof |
|---|---|---|---|---|
| `tests/api/test_storage_manager.py` | 31 (17 failed + 14 errors) | `MINIO_ENDPOINT` default `minio:9000`; CI has no object storage: `urllib3 NameResolutionError … Failed to resolve 'minio'` | CI environment | 31 pass against an S3 stand-in; all pass in CI run #11. |
| media (5), documents (5), expense claims (5), backups (2), monitoring health check (1) | 18 | same | CI environment | pass against the stand-in and in CI. |
| `test_integrations::test_connection_test_records_real_success`, `test_storage_public_urls::…` | 2 | Need a real MinIO (health endpoint `/minio/health/live`; signed-URL enforcement) | CI environment | fail on the stand-in (404 / forged URL accepted), **pass in CI run #10/#11 on real MinIO**. |
| `test_hackathon_ai_evaluation` (14), `test_hackathon_award_certificates` (8), `test_hackathon_certificates` (5) | 27 | The code needs the seeded `hackathon_participant` role (`modules/hackathons/provisioning.py`: "The 'hackathon_participant' system role is not seeded on this ERPX instance"). `test_hackathon_participants.py` declares `pytest.mark.usefixtures("rbac_seeded")`; the three files reuse its helpers but only had `pytest.mark.api`. They passed on a developer database that an earlier test or the dev seed had already populated. A fresh migrated database has 0 roles. | Outdated test assumption (test isolation) | Fresh DB: 27 failed / 25 passed; with the fixture applied via `-o usefixtures=rbac_seeded` (no file change): 52 passed; after the PR #164 change each module passes alone. |
| `tests/integration/test_storage_manager_migration.py` | 1 | Test upgraded to `head` and asserted exactly `0095 → 0096`; later migrations exist (head `0100`; 0097 already broke it) | Outdated test assumption | After the fix: passes; and in CI. |
| `test_a_team_is_joined_only_with_its_code…` | 0 locally, 1 in CI run #10 | The staff team list is ordered by `created_at asc` (`modules/hackathons/repository.py` line 100) but all requests in a test share one open transaction (`tests/_fixtures.py` `db_session`) and Postgres `now()` is the transaction start time, so two teams in one test get an identical `created_at` and arbitrary order. Demonstrated: `now()` stays at transaction start after a 50 ms wait. 12 of 12 local runs passed before and after, so the flake rate was **not** reproduced locally. | Test harness artifact (not an application defect: each production request has its own transaction) | Run #11 passed. |
| `tests/integration/test_restore_backup_integration.py` (2 compressed-archive tests) | 0 locally, 2 in CI | **Not fixed. Not reproduced.** See 6. | CI environment (likely) | — |

None of the 79 is a payment, internship, Cashfree or dependency-compat test, and PR #163 touches none of those test files.

## 5. What PR #164 contains (GIT)

Commit `64a04af` "CI repair: test isolation for hackathon modules and the 0096 migration test, isolated MinIO for the backend job" and commit `827385c` "Tests: do not depend on the order of two teams created in one test transaction". Files:

- `tests/api/test_hackathon_ai_evaluation.py`, `test_hackathon_award_certificates.py`, `test_hackathon_certificates.py`: `pytestmark = [pytest.mark.api, pytest.mark.usefixtures("rbac_seeded")]`.
- `tests/integration/test_storage_manager_migration.py`: `upgrade 0096` (not `head`) both times; the assertion `Running upgrade 0095 -> 0096` is unchanged; the rollback to `0095` and exact-shape comparison are unchanged.
- `tests/api/test_hackathon_participants.py`: the staff list assertion compares `sorted(listed) == sorted([code, blue["join_code"]])` with an explanatory comment.
- `.github/workflows/ci.yml`:
  - triggers include `master`; `PYTHONPATH: ${{ github.workspace }}` on the migration step;
  - job-level env `MINIO_ENDPOINT=127.0.0.1:9000`, `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` (throwaway values defined in the workflow file), `MINIO_BUCKET=erpx-ci-tests`, `MINIO_SECURE="false"` (throwaway values for a container that exists only for the job);
  - step "Start isolated MinIO": `docker run -d --name erpx-ci-minio -p 127.0.0.1:9000:9000 -e MINIO_ROOT_USER … -e MINIO_ROOT_PASSWORD … pgsty/minio@sha256:b6bfe7239bfc83fb90d31612d9704d86039dd714f7904b3f1ad68f211e602372 server /data`, then `curl --fail --retry 30 --retry-delay 2 --retry-connrefused --retry-all-errors` against `/minio/health/live` and `/minio/health/ready` (no fixed sleep; on failure it prints `docker logs` and exits 1);
  - step "Create the test bucket" (Python `minio` client, asserts the bucket exists);
  - step "Stop MinIO" with `if: always()`;
  - pip-audit scan and gate steps get `if: ${{ !cancelled() }}` so a failed test step no longer hides the gate (the gate script and its Critical/High threshold are unchanged).
- **The MinIO image pin (verified 2026-11-03 by hashing):** the digest is the Docker Hub manifest index of `pgsty/minio:RELEASE.2026-08-04T00-00-00Z`; fetching `https://registry-1.docker.io/v2/pgsty/minio/manifests/<digest>` with the index Accept header returned `docker-content-digest: sha256:b6bfe7…2372` and `sha256sum` of the body matched. Platforms: linux/amd64 `sha256:2b36182f…68db9`, linux/arm64 `sha256:1026039c…09f17`. Entrypoint `/usr/bin/docker-entrypoint.sh`, Cmd `minio`, port 9000. To update: look up the new tag's index digest the same way and re-verify. `minio/minio` itself cannot be pulled any more (UNVERIFIED on production). The Docker Hub registry rate-limits (HTTP 429) unauthenticated bursts.
- PR #164 changes **no application code, dependency, payment code, production MinIO or production Docker Compose**.

## 6. The remaining backend failures: the PostgreSQL restore tests

Symptom (GH): `restore_backup` exits `RESTORE_FAILED` (6) for `pg_restore` of a `pg_dump -Fc` archive made by the test itself into a throwaway database. The PostgreSQL 16 service log in the same CI runs shows, around the time those tests run: `ERROR: unrecognized configuration parameter "transaction_timeout"` / `STATEMENT: SET transaction_timeout = 0;` (two occurrences per run, matching two failing tests).
Interpretation (**strongly suggested, not proven**): the GitHub runner's `pg_dump`/`pg_restore` is newer than the server (the `transaction_timeout` setting exists from PostgreSQL 17), and a newer client sends a `SET` that the PostgreSQL 16 service rejects. `apps/api/scripts/restore_backup.py` strips version-skew `SET` lines only for **plain** SQL dumps (`sanitize_dump_for_restore`; "a compressed archive is restored as it is"), and the plain-format restore tests pass. The runner client version was never printed. Locally (Cloud) both tests pass with client 16 = server 16. The owner's `docs/CLOUD_HANDOFF.md` §9 says the backup tests "need `pg_dump`/`pg_restore` 17 on the PATH" and lists "give CI … a Postgres 17 client". UNVERIFIED: why that works on the owner's machine (check client and server versions there).

Why it matters beyond CI (UNVERIFIED hypothesis, worth a rehearsal): the production API image installs `postgresql-client` from Debian trixie, which "ships pg_dump 17" against a PostgreSQL **16** server (`apps/api/Dockerfile` comment), and in-app backups default to compressed (`BACKUP_FORMAT=custom`, `modules/backups/service.py`). If a client-17 `pg_restore` into a 16 server emits the same `SET`, a compressed-archive restore through `restore_backup.py` could fail in production disaster recovery. Do not assume either way: test it on a non-production copy (owner's `docs/operations/disaster-recovery-runbook.md` and `offsite-backup.md`, `restore_verify.sh`).

Proposed fixes, in order (none implemented):
1. Add a diagnostic CI step that prints `pg_dump --version`, `pg_restore --version`, `psql --version` and the service server version (harmless, permanent, tells the truth). Needs one CI run.
2. If the client is newer than 16: install `postgresql-client-16` on the runner (apt, PGDG repo) and put `/usr/lib/postgresql/16/bin` first on `PATH` for the test step (matches the production server), **or** run the service as `postgres:17-alpine` (diverges from production's 16). Prefer matching production.
3. Separately, decide whether `restore_backup.py` should also tolerate version skew for compressed archives (that is application/ops code: owner decision, own PR, test on a copy).

## 7. Conflict between PR #163 and PR #164 (GIT, `git merge-tree`, 2026-11-03)

Both branches edit `.github/workflows/ci.yml`. The trigger lines and the `PYTHONPATH` lines are identical and merge cleanly, but **the adjacent hunk conflicts**: #163 adds the "Check Celery / Kombu / redis-py compatibility" step (3 comment lines + step) where #164 adds the MinIO comment block, "Start isolated MinIO" and "Create the test bucket" steps. The text in PR #164's description that the shared lines "merge cleanly" is true for those lines only; the PR as a whole conflicts with #163. #162 does not conflict with either.
Resolution when the second of the two merges: keep **all** of both: after "Install backend dependencies" keep the compat step (its `--broker redis://localhost:6379/1` uses the Redis service, unaffected by MinIO), then "Start isolated MinIO", "Create the test bucket", "Run migrations" (with `PYTHONPATH`), "Run backend tests", "Stop MinIO", then the pip-audit steps.
Recommended merge order (owner decides; nothing merges automatically): **#164 first** (tests and CI only; no application change; independent of Cashfree), then rebase/merge `master` into #163 and resolve that one hunk, then re-run CI on #163 (its Celery check and the payment tests should then run in a green-as-possible pipeline). #162 is independent and may go any time after review.

## 8. Security advisories (separate PRs; nothing upgraded yet)

### 8.1 npm (checked with `npm audit --json` at the PR #163 head on 2026-11-03; registry data from the same day; re-check)
Counts: `web` 28 (22 moderate, 4 high, 2 critical); `student-portal`, `trainer-portal`, `corporate-portal` 24 each (20 moderate, 2 high, 2 critical). The gate (`npm audit --audit-level=high`) fails on:

| Advisory | Package (locked) | Severity | Reachable in production? | Safe path found |
|---|---|---|---|---|
| GHSA-5gmw-xhrv-c9v3, GHSA-85c8-ppgw-ccpr (prototype pollution → RCE) | `tinypool` 1.1.1 via `vitest` 3.2.6 | critical | No: test tooling | `vitest` 4.1.12 removes the `tinypool` dependency (also fixes GHSA-82fw-gwwq-j7x9, vitest ≥2.1.0 <4.1.11). **Not** `vitest@5.1.0`, which `npm audit` suggests: it needs Node ≥22.12 while CI and the Docker images use Node 20. vitest 4 needs `vite` ≥6. |
| GHSA-4w7w-66w2-5vf9, -v6wh-…, -698v-…, -r825-…, -587h-… (high), -9jrq-…, -rq7h-…, -fx2h-… (vite dev server, launch-editor; mostly Windows or dev-server) | `vite` 5.4.21 | high | No: dev server | `vite` 6.4.5 (Node 18/20/22 OK; `@vitejs/plugin-react` 4.7 supports vite 4 to 7). `npm audit` suggests 8.3.5 (needs Node ≥20.19). |
| GHSA-mrhx-c7xc-m3w5 (memory exhaustion validating oversized constrained collections) | `zod` 3.25.76 | high | Yes: runtime code (77 files import zod in `web`, 1 file in each portal) | The listed fix is `zod` 4.6.7 (a major migration; the owner's `docs/CLOUD_HANDOFF.md` §7 says it needs `@hookform/resolvers` 5 and about 175 files in `web`; the latest `@hookform/resolvers` 7.0.1 declares a peer of zod `^3.25 \|\| ^4`; the Cloud did not test any of this). Whether zod **3.x** is truly affected could not be read (advisory page blocked); the advisory range is `<4.6.6`. Treat as an owner decision: migrate, or a scoped, documented, expiring exception. |
| GHSA-834v-8h66-3h79, GHSA-c8p4-j97h-3vg8 (SSRF, import alias) | `happy-dom` 20.14.6 via `@tiptap/html` 3.32.0 (**web only**) | high | Only if untrusted HTML is parsed on a server | `happy-dom` 21.0.4 with `@tiptap/html` 3.32.2 (peer `^20.8.9 \|\| ^21.0.4`): in-range, lockfile-level. This corrects `docs/CLOUD_HANDOFF.md` §7, which said "no upstream fix". |
Moderate-only items (the eslint chain, esbuild, react-router, etc.) do not fail the gate.

### 8.2 pip-audit (`pip-audit -r requirements.txt` at the PR #163 head; confirmed in CI runs #10 and #11)
13 findings in 4 packages (severity from OSV via `.github/scripts/pip_audit_severity_gate.py`): **`pypdf` 6.21.2: 7 HIGH** (CVE-2026-119203, -119204, -119205 fixed in 6.21.4; CVE-2026-119206, -119207, -119208, -119209 fixed in 6.21.3), `aiosmtplib` 3.0.2 MODERATE (PYSEC-2026-2338, PYSEC-2026-3805; fixes 5.1.1/5.1.2), `opentelemetry-api` 1.44.0 MODERATE (CVE-2026-114603; fix 1.45.1), `pytest` 8.3.3 MODERATE (PYSEC-2026-1845; fix 9.0.3). Only the `pypdf` items fail the gate. A `pypdf` patch bump (6.21.2 → 6.21.4) is the small, targeted change; run the PDF-related tests (certificates, offer letters, bulk exports, financial documents) after it. PR #157 had brought the gate to 0 Critical/High on 2026-10-30; the new `pypdf` advisories are newer than that.

## 9. How to read CI results from the Cloud (what worked) and from Local

Cloud: the log tool returns only the tail and the job log ends with PostgreSQL service-container output, so the pytest summary sits about 700 lines from the end; request `return_content=true` with `tail_lines=700` (the result is saved to a file) and filter lines starting `FAILED`/`ERROR tests`, `=====`, `##[error]` and the "pip-audit severity report" block. The log blob host and OSV were blocked. **Local (recommended):** `gh run view <id> --log-failed`, `gh run download <id>` (the audit reports are uploaded as artifacts `pip-audit-report` and `npm-audit-report-<app>`), or the Actions web page.

## 10. Local reproduction recipes (use your own throwaway database; never the real one)

```bash
# 1) a disposable PostgreSQL 16 + Redis (not your development database)
#    CI uses postgres:16-alpine (db erpx_test, user erpx) and redis:7-alpine
# 2) fresh schema, same as CI
cd apps/api
DATABASE_URL=postgresql+asyncpg://<user>:<pw>@localhost:5432/<throwaway_db> PYTHONPATH=<repo root> alembic upgrade head
# 3) MinIO for the storage tests (pinned image above), then
export MINIO_ENDPOINT=127.0.0.1:9000 MINIO_ACCESS_KEY=<throwaway> MINIO_SECRET_KEY=<throwaway> MINIO_BUCKET=erpx-ci-tests
# 4) only the relevant tests (the full suite takes 15 to 40 minutes)
pytest -q --no-cov tests/api/test_hackathon_ai_evaluation.py tests/api/test_hackathon_certificates.py tests/api/test_hackathon_award_certificates.py
pytest -q --no-cov tests/integration/test_storage_manager_migration.py tests/integration/test_restore_backup_integration.py
```
Useful tricks proven in the Cloud: `-o usefixtures=rbac_seeded` applies a fixture to every test without editing files; `pytest -p no:logging --no-cov --tb=line` keeps output short; a test database with 0 roles reproduces the hackathon failures.
For the restore tests, compare `pg_dump --version`, `pg_restore --version` and `SHOW server_version;` and try client 16, 17 and 18 against a 16 server. Report the matrix.

## 11. Facts about the CI environment (GH)

Runner `ubuntu-latest`; Python 3.12.15 (`actions/setup-python@v5`, pip cache keyed on `apps/api/requirements.txt`); services `postgres:16-alpine` (user `erpx`, db `erpx_test`) and `redis:7-alpine` (7.4.12); Node 20; frontend matrix `fail-fast: false`; `pip-audit` installed unpinned at run time; Node.js 20 action deprecation warnings only. Backend job time: install about 25 s, MinIO start about 6 s, migrations about 5 s, tests 16 to 26 minutes.

## 12. Do not

- Do not skip or disable tests, loosen `npm audit --audit-level=high`, change the pip-audit Critical/High threshold, or remove the `!cancelled()` guard to get green.
- Do not blindly run `npm audit fix --force` (it proposes Node-22-only and major jumps).
- Do not mix the dependency upgrades into #163 or #164; one concern per PR.
- Do not push to #163/#164 branches unless deliberately continuing those PRs.
