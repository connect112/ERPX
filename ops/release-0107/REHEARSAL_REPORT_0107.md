# Release 0107: sanitized staging-rehearsal evidence (local, isolated)

Scope: the code-only rollback `90_rollback_code_only.sh` (modes `full`, `forward`) run for real, on a real Docker daemon, with synthetic data only. Nothing
here touched production, AWS, real student data or the development database. No credentials, tokens, addresses of real systems or personal data appear
below; passwords inside the rehearsal were random and are not recorded. Two rounds were run; round 2 repeats the part that changed.

## 1. Isolation (both rounds)
| Item | How |
|---|---|
| Daemon | one container (`docker:27-dind` + bash, coreutils) running its own Docker daemon, v27.5.1 (the host's is a different daemon, v29.6.2); `--privileged` is the one compromise (inside Docker Desktop's Linux VM) |
| Network | `--network none` (no network, no egress; checked: no route out). A separate internal network could not be created (Docker's address pools were exhausted), and no existing network was touched |
| Mounts / ports | one new named volume for the inner daemon's storage; no bind mounts, no host Docker socket, no published ports; no secret-like variables in the environment |
| Stack inside | `docker-compose.prod.yml` of this repository (project `erpx-prod`, `webnet`), shared Postgres 16 and Redis 7 containers, MinIO, api / celery worker / beat, three nginx stand-ins for the frontends |
| Images | 0107 api built from this repository; previous api built from commit `3a722a6`; others loaded from the local daemon (`docker save | docker load`) |
| Data | empty database migrated to revision 0107, then the synthetic seed `scripts.seed_learning_e2e` (fake cohort of students, an instructor, an administrator); four internship-private records (assessment, thread, practical, viva) and four course-wide ones created through the application's own API |
| Cleanup | rehearsal container, volume and images removed; development environment compared with its baseline: identical containers, start times and restart counts, networks, volumes, and an identical per-table row-count hash of the development database |

## 2. Round 1 (script at commit `87fae07`)
| # | Scenario | Command (inside the private daemon) | Exit | Result |
|---|---|---|---|---|
| 1 | complete rollback | `MODE=full bash 90_rollback_code_only.sh` | 0 | PASS=13 FAIL=0. Order in the log: beat stopped, api stopped, worker stopped, zero application DB sessions, safety dump, hold, guarded previous api started and its guard confirmed three ways |
| 2 | private records hidden | HTTP as cohort student, independent enrolee, administrator | n/a | after the rollback each sees only the course-wide quiz, thread, practical and viva; direct request for the private assessment: 404 |
| 3 | cross-student reads | HTTP `GET /examinations/results/{s}/course/{c}` and `/lms/progress/{s}/course/{c}` | n/a | student A to B, B to A, independent enrolee to A: **403** (both endpoints); own: 200; administrator: 200; no login: 401 |
| ctl | control | same previous image, no guard, hold undone on a copy of the database | n/a | independent enrolee sees all four private records; every cross-student read **200** (proves the probes can see a leak) |
| 4 | interruption | `MODE=full` killed with SIGKILL right after the hold committed, then `MODE=full` again | 137, then 0 | after the kill: writers stopped, no private record visible; recovery PASS=13; ledger unchanged (hold idempotent), 0 duplicate open ledger rows |
| 5 | api cannot be stopped | `MODE=full` with an outside writer creating a private assessment after the previous api started and `docker stop erpx_api` made to fail | **9** | CRITICAL message, no "safe" wording, docker confirmed `Running=true`. **The still-running previous api served `LATE PRIVATE Quiz` to the independent enrolee**: the exposure this change prevents (section 3). After a manual stop, `MODE=full` exit 0 and the record was held |
| 6 | roll forward | `MODE=forward` (three times) | 0 | PASS=7 each; ledger fully released; cohort sees the private records again on the 0107 app |
| 7 | preservation | per-table row counts and content hashes (261 tables), volumes, container start times, MinIO objects | n/a | see section 4 |

## 3. Round 2: the late-writer trap (script and SQL of this change)
The hold now also installs a trigger on the four tables that parks a private row as it is written (`sql/rollback_hold.sql`; design and alternatives in the checklist, part 4.3).
| Scenario | Command | Exit | Result |
|---|---|---|---|
| complete rollback | `MODE=full` | 0 | PASS=14 FAIL=0 (includes "late-writer trap installed on all four tables", 4 triggers) |
| rehearsal scenario 5, repeated exactly | `MODE=full` with the same late writer and the same failing `docker stop` | **0** (round 1: 9) | the late assessment is parked under the soft-deleted holding course and on the ledger; the previous api is up; the independent enrolee and the cohort students see only course-wide content; cross-student reads still 403 |
| roll forward | `MODE=forward` | 0 | PASS=7; 0 triggers and 0 trap functions left; 0 open ledger rows; the late record is back under its original course |
| preservation | snapshot diff, baseline vs final | n/a | hold-affected tables `lms_discussion_threads`, `exam_practicals`, `exam_vivas` byte-identical (same hashes); `lms_assessments` identical once the one injected record is excluded; volumes, MinIO sentinel object (same ETag) and Postgres/Redis/MinIO start times unchanged |

Automated tests added with this change (all pass): `tests/unit/test_rollback_trap_sql.py` (14, real PostgreSQL: late insert and update parked on all four tables, course-wide rows untouched, idempotent hold, release removes the trap and restores every row, application-role writer without rights on the ledger is still parked, failure without `SECURITY DEFINER` shown); `tests/unit/test_rollback_90.py` (22, stub docker: trap checked at hold, verify, resume and forward); `tests/unit/test_rollback_real_image.py` (16, **real previous image over HTTP**: with the old hold SQL a late record is served to an independent enrolee, with the trap no student sees it, course-wide content and staff access unchanged, cross-student reads still 403).

## 4. Preservation checks (round 1 after three rollback/forward cycles, one crash, one stop failure; round 2 equivalent)
- Tables that changed: `audit_logs`, `refresh_tokens`, `users` (logins made by the probes); `courses` +1 (the soft-deleted holding course, kept as an audit trail); `lms_assessments` +1 (the injected late record, in the round that had one); `role_permissions` and `social_job_runs` (change on any plain restart of the 0107 api: startup seed and beat jobs, reproduced without any rollback). No table added or removed (261 = 261).
- Unchanged: `students`, `lms_enrollments`, `internship_selections`, `our_internships`, result and attempt tables (rows and content hash), the three volumes (names, creation times), MinIO object list and ETag, Postgres/Redis/MinIO containers never restarted, five pre-hold safety dumps kept.

Content hashes (md5 over the rows of the table, sorted; synthetic data), baseline = final in both rounds for the three tables below:
| Table | Round 1 | Round 2 |
|---|---|---|
| `lms_discussion_threads` (2 rows) | `fdcfcc5d08ea2aeb1b083d2d9e8e04cb` | `6cd6bc3a503272f4fa31843c13e7e098` |
| `exam_practicals` (2 rows) | `184c21678f45123a2c8041beffecf4bd` | `4e91681c840c733ac2e6880f1f454358` |
| `exam_vivas` (2 rows) | `f2d2036d8c94ea6c1d16a1b4988ae96a` | `0a80e1adbd38fd981a4717d115783f31` |
| `lms_assessments` (original 2 rows) | `e065160ed5ed8960665f88fa16c09c58` | `d93479e1999a3cd466aab76baacb19be` |
(the values differ between rounds only because each round has its own freshly generated synthetic ids). MinIO sentinel object ETag unchanged: `dad19cf653b8aa5bf2e2c9e83b527434`.

## 5. Limitations (what this does not show)
- Frontends were nginx stand-ins; compose `build:`, Caddy, S3 off-site backup checks, systemd and `04_post_deploy_verify.sh` were not run. `DRY_RUN` and `MODE=release` were exercised by unit tests only.
- Round 2 ran the trap as a database superuser (the rehearsal's writer); the application-role case is covered by the PostgreSQL test, not by a third Docker round.
- The trap hides a private write, it does not reject it, and does not stop non-private writes of a stray 0107 api. Database lock-out (`NOLOGIN` / connection limit) is designed and tested on a throw-away server but **not implemented** (needs approval).
- The zero-session check remains a point-in-time check of one database role.
- The rehearsal ran on one machine (Apple silicon, arm64 images); production is a different host with real data volumes and traffic.
- Cosmetic finding, not fixed: verify lines for non-api services print the service name appended to "previous release's image".
