# ERPX PR #180 — release 0107: GO/NO-GO, deployment, verification, rollback

**Status: prepared and rehearsed on a copy; nothing has been run against production.** Every script here was executed only against an isolated local
PostgreSQL (revision 0106 and 0107 copies) with the production container names routed to it and `aws`/`systemctl` faked, so no AWS or production
call was possible. Production itself has never been touched. Merge, deploy and migrations need your approval.

| File | Does what | Writes? |
|---|---|---|
| `00_preflight_readonly.sh` | revision, disk, off-server backup, long transactions, in-progress exams, two data reports | **No** (database-enforced read-only) |
| `01_deploy_api.sh` | gates → source fast-forward → save images + baselines + verified dump → build and recreate **api only** (runs migration 0107) | yes (deploy) |
| `02_deploy_workers.sh` | worker and beat | yes (deploy) |
| `03_deploy_frontends.sh` | `web`, `student_portal`, `trainer_portal` | yes (deploy) |
| `04_post_deploy_verify.sh` | automatic checks, counts against baseline, PDF libraries in the containers | **No** |
| `90_rollback_code_only.sh` | code-only rollback with containment, and roll-forward | yes (rollback) |
| `sql/rollback_hold.sql`, `sql/rollback_release.sql`, `rollback_guard/*.py` | the SQL and the two guard files embedded in `90_…` (a test keeps them equal; regenerate with `wip/build_90_v2.py`) | yes (rollback) |

Run any script with `DRY_RUN=1` first to see every command without running it. Scripts are pasted into AWS Systems Manager → Run Command →
`AWS-RunShellScript`, targeted at the production instance only, as in the 2026-10-30 release.

---

## 1. Before the window

### 1.1 GO / NO-GO gates (every one must be GO)

| # | Gate | GO when | NO-GO when |
|---|---|---|---|
| G1 | Approval | You approved merge; PR #180 is out of draft, reviewed, merged; CI is green **on the merge commit**; you have its 40-character SHA | any of these missing |
| G2 | Preflight | `00_preflight_readonly.sh` ends with `FAIL=0` | any `[FAIL]` line |
| G3 | Revision | production `alembic_version` is exactly what you will pass as `EXPECT_REV_BEFORE` and is **below** 0107 | at 0107 or higher, or unreadable |
| G4 | Backup | newest `daily/` folder is ≤ 27 h old **and** has `SHA256SUMS`; `offsite-backup.timer` active | older, unfinished, or timer inactive |
| G5 | Disk | free ≥ the larger of 4 GB and 2× the database size | less |
| G6 | Transactions | none open > 5 min at the moment you start (`01` re-checks) | any |
| G7 | Exams | preflight shows no exam or quiz attempt in progress; open internship exams (report E) understood | attempts in progress (reschedule) |
| G8 | Data reports | you read reports F and G and decided what to do about the students they list (personal exam links of students without granted access stop working; shared e-mails need re-assignment) | not read |
| G9 | Baselines | you saved the PDFs in 1.3 | not saved |
| G10 | Rollback | you read part 4 and `90_rollback_code_only.sh` with `DRY_RUN=1`, and a person is available for the whole window | no |

### 1.2 The four verifications, one command each (all read-only)

**Production migration revision**
```bash
docker exec -i -e PGOPTIONS="-c default_transaction_read_only=on" shared_postgres psql -X -U postgres -d erpx -tA -c "select version_num from alembic_version"
docker exec -e PYTHONDONTWRITEBYTECODE=1 erpx_api alembic heads        # the head the RUNNING image knows
```
Pass: the first value is the revision you pass as `EXPECT_REV_BEFORE` (0106 if the earlier releases are in). Below 0104 means 0104–0106 ship too: read report F.

**Latest off-server backup**
```bash
B=s3://pentrix-erpx-backups-373384939117/daily
N=$(aws s3 ls $B/ | awk '$1=="PRE"{print $2}' | tr -d '/' | sort | tail -1); echo "newest: $N"
aws s3 ls $B/$N/                                  # must list SHA256SUMS (written last) and manifest.json
echo "age: $(( ( $(date -u +%s) - $(date -u -d "$N 03:30" +%s) ) / 3600 )) h"      # must be <= 27
systemctl is-active offsite-backup.timer; cat /opt/backups/offsite/last_status.json
```
This proves the backup **finished** and is **fresh**. It does not prove it can be **restored**: do that off the server, as `docs/operations/offsite-backup.md`
says, with a read-only AWS profile: `AWS_PROFILE=<read-only profile> ops/offsite-backup/restore_verify.sh` (newest complete backup) if the last restore check is older than a week.
`01_deploy_api.sh` additionally takes its own verified dump (`pg_restore --list` must read it) just before the migration: that is the fast recovery point.

**Available disk space**
```bash
df -h /; df -B1 --output=avail / | tail -1
docker exec -i -e PGOPTIONS="-c default_transaction_read_only=on" shared_postgres psql -X -U postgres -d erpx -tA -c "select pg_size_pretty(pg_database_size(current_database()))"
docker system df
```
Pass: free ≥ max(4 GB, 2 × database size). (The pre-migration dump and three image builds are what need the room.)

**Long-running transactions**
```bash
docker exec -i -e PGOPTIONS="-c default_transaction_read_only=on" shared_postgres psql -X -U postgres -d erpx -c "select pid, state, now()-xact_start as open_for, left(query,70) from pg_stat_activity where xact_start is not null and now()-xact_start > interval '1 minute' and pid <> pg_backend_pid() order by xact_start"
docker exec -i -e PGOPTIONS="-c default_transaction_read_only=on" shared_postgres psql -X -U postgres -d erpx -tA -c "select count(*) from pg_locks where not granted"
```
Pass: no rows, and 0 waiting locks. The migration adds foreign-key columns, which takes a short lock on `users`, `our_internships` and `our_internship_selections`; a long
transaction on any of them would make the migration wait and stall writes behind it.

### 1.3 Baselines to save (so "the PDFs look the same" is a comparison, not a memory)
As a plain Administrator, download and keep: **one existing offer letter PDF, one existing receipt PDF, one existing payslip PDF** (and note their ids). After the deploy, regenerate or re-download
the same documents and compare (page count and text must match; open both and look):
```python
# python -I compare_pdf.py before.pdf after.pdf        (pip install pypdf)
import sys; from pypdf import PdfReader
a, b = (PdfReader(p) for p in sys.argv[1:3])
print("pages:", len(a.pages), len(b.pages), "| text identical:", [p.extract_text() for p in a.pages] == [p.extract_text() for p in b.pages])
```

---

## 2. Deployment (about 20–30 minutes; one person watching the output)

1. **Preflight** (`00`). Paste the output into the approval thread. GO/NO-GO per 1.1.
2. **Step 1 — `01_deploy_api.sh`**: set `SHA` (merge commit) and `EXPECT_REV_BEFORE`. It refuses unless the gates hold, saves rollback images (`erpx-rollback/*:pre-0107-<ts>` and
   `/opt/backups/pre-release/images-0107.env`), writes `baseline-counts-0107.txt`, takes and verifies the dump, builds and recreates `api` only. **Checkpoint C1** must show:
   `alembic_version: 0107`, health 200, `new columns present: 10 of 10`, `lms_assessment_questions exists: true`, no error lines. If the api is not healthy: stop, read the log it prints, then part 4.
3. **Step 2 — `02_deploy_workers.sh`** (same `SHA`): worker, beat. **C2**: worker healthy, `celery ping` answers, `reportlab 4.4.3 svglib 2.3.1`.
4. **Step 3 — `03_deploy_frontends.sh`** (same `SHA`): web, student portal, trainer portal. **C3**: all three `running`, each answers HTML.
5. **Step 4 — `04_post_deploy_verify.sh`** → must end `FAIL=0`.
6. Manual checks (part 3). Then, and only then, declare the release good.

Steps 1–3 follow the proven 2026-10-30 pattern (pre-migration dump, tagged rollback images, `--no-deps`). Employee portal and Pentrix are not touched.

---

## 3. Post-deployment verification

**3.1 Automatic:** `04_post_deploy_verify.sh` (revision, health, containers, every business table has not shrunk against the baseline, nothing parked, no payment/e-mail/error lines in logs, PDF libraries render in both containers, backups still scheduled).

**3.2 Manual** (use a plain Administrator for admin screens; use an internal or consenting test student, never a real student's account). Nothing below sends an e-mail or creates a payment.

| Area | Do | Expected |
|---|---|---|
| **Student login** | Student portal → sign in → My Courses → open an internship course and an ordinary course | signs in once (single sign-on across sites still works); courses list; lessons open; no error banner; browser console has no red errors |
| **Student isolation** | As an independent enrolee of a course that serves an internship, open that course | the internship's private quiz is **not** listed |
| **Revoked access** | As a student whose internship access was withdrawn | the internship course is gone; their earlier results remain visible to staff, marked "revoked" |
| **Examinations** | Open an existing **non-internship** exam's personal link in a private window (do not submit) | loads normally. For an internship exam: a granted student's personal link loads; the link of a student without granted access shows "not found" (by design; those names were in report G) |
| **Public sign-up link** | Open the public sign-up link of an OPEN internship exam, if report E listed any | refuses new people with "assigned by the internship team" (by design); ordinary workshop/hackathon exams still register |
| **Resource access** | Admin: Courses → a course → Curriculum → open an existing link resource; student portal: open the same lesson's resources | links open. Optional (needs a throwaway unpublished course/lesson): upload a 1 KB PDF, download it as a student, delete it → the file downloads, and delete removes it |
| **Offer-letter PDFs** | Admin → Our Internships → internship → **Offer letters** → **Preview** (sample or a real student, from the saved settings). **Do not press Generate or Release.** Open an existing generated letter too | preview PDF: logo (an SVG logo too), selectable text, two pages for the reference content, watermark/signature as configured; matches the baseline from 1.3; the existing letter still opens |
| **Receipts** | Admin → Accounting → **Receipts** → open an existing paid receipt; Receipt designer → Preview | PDF identical in layout and text to the baseline from 1.3 |
| **Payslips / other PDFs** | open the saved payslip | same as baseline |
| **Existing payments (read-only)** | Admin: the internship payment settings/account show as before (same screen you use today); open an existing order and transaction; `04` shows payment tables unchanged. Webhook reachability: `curl -s -o /dev/null -w "%{http_code}\n" -X POST -d '{}' https://<your-domain>/api/v1/public/payments/cashfree/webhook` | account/orders unchanged; the webhook answers a **4xx** JSON (bad signature), never 404 or 5xx. This PR does not change payment code; these checks guard the shared infrastructure and the PDF libraries |
| **Certificates** | open an existing certificate/eligibility record; download an issued certificate | unchanged |
| **Learning workspace** | Admin: Our Internships → an internship → Learning, and Courses → the same course → Learning | the same seven tabs, in order: Curriculum, Enrollments, Evaluations, Projects, Discussions, Practicals, Viva |
| **Trainer portal** | An instructor: Internships → Open learning | seven tabs; no Delete buttons; curriculum is read-only |

An optional real ₹1 payment-and-refund test is **your** decision and your card; nothing in this pack creates one.

---

## 4. Rollback

### 4.1 When
**Roll back (code only)** if, after Step 1, any of: the new api never becomes healthy and cannot be fixed within minutes; students cannot sign in; payment webhooks answer 5xx or the verifier shows payment failures;
offer-letter or receipt PDFs fail; `04` shows a table that shrank. **Fix forward instead** for cosmetic issues, a wrong label, or a single screen.
If the **migration itself failed**, the database is still at the old revision (it runs in one transaction): use `MODE=full` (it sees the schema is not at 0107, skips the hold, and only restores the images; the guarded api image is still used).

**Never run `alembic downgrade 0106`**: it drops the question rows, attempt answers, cohort scoping and upload metadata created since the release, and orphans uploaded files.
A restore of the pre-release dump is the last resort, needs its own approval, and loses everything written since the dump.

### 4.2 Why a plain image swap is unsafe (both proven in rehearsal, on real rows)
1. **Private content would be exposed.** The previous code lists assessments, discussion threads, practicals and vivas by course alone, and every student may list them. With old code on the 0107 schema, an independent enrolee saw `PRIVATE Quiz`, `PRIVATE thread`, `PRIVATE practical`, `PRIVATE viva`.
2. **The previous api would crash-loop.** Its entrypoint runs `alembic upgrade head` (`RUN_MIGRATIONS=true`) and alembic stops with `Can't locate revision identified by '0107'`.

### 4.3 The procedure
```text
90_rollback_code_only.sh   with MODE=full on its first line     (run it once with DRY_RUN=1 to read the plan; every command that would change something is printed with a +)
```
In order, and the order is enforced by the script and by `tests/unit/test_rollback_90.py`:
1. **Preflight, changes nothing**: the saved images exist, docker and the database answer, the revision is not ahead of 0107, 1 GB is free.
2. **Guarded image**: a derived image is built FROM the saved previous api image with exactly two files replaced (`modules/examinations/results/routes.py`, `modules/lms/progress/routes.py`; section 4.5). It refuses, changing nothing, unless both files it replaces are byte-for-byte the previous release's.
3. **Save the 0107 images** (needed for `MODE=forward`).
4. **QUIESCE, before any data is touched**: stop `erpx_celery_beat`, stop `erpx_api` (in-flight requests get `API_GRACE` s), wait for `erpx_celery_worker` to finish its running tasks (up to `WORKER_DRAIN` s) and stop it. Queued tasks stay queued. Then it requires **zero** database sessions of the application user (`APP_DB_USER`, default `erpx`); if any remain it stops with exit 5 and **the hold is not run**.
5. **Hold**: a verified safety dump of the five affected tables, then every internship-private row is moved, unchanged, under a soft-deleted holding course of the same organization (the previous code treats a deleted course as "not found"). Each move is recorded in `ops_0107_rollback_hold`; the transaction checks that nothing private remains under a visible course or rolls back. **The same transaction installs the late-writer trap** (four triggers) so a private record written later is parked as it is written, and rolls back unless all four exist.
6. **Restore** the six saved images (the api from the guarded image) with `RUN_MIGRATIONS=false` through `/opt/backups/pre-release/rollback-api-override.yml`, then confirm the guards in the **running** api three ways (image label, file hash inside the container, the route's code). If they cannot be confirmed the api is **stopped again** (fail closed, exit 7).
7. **Verify, read-only** (also available alone as `MODE=verify`).
The database stays at 0107; nothing is dropped or deleted. An interrupted run is finished by running it again with the same MODE.

Modes: `full` (the rollback), `forward` (stop the writers, release the hold, start the saved 0107 images), `verify` (read-only checks of the rolled-back state), `release` (only the hold-release SQL; refuses unless the 0107 api is the one running).

**Verified by execution:** the stub tests (`tests/unit/test_rollback_90.py`) show that at the moment the dump and the hold SQL reach the database the api, worker and beat are all stopped, that remaining sessions block the hold, that a wrong previous image changes nothing, that unconfirmed guards stop the api again, that an interrupted run resumes, and that `forward` stops the writers before releasing. `tests/unit/test_rollback_real_image.py` runs the **real previous image** (built from `3a722a6`) with and without the guards over real HTTP against a scratch copy of the 0107 database.

**Exit codes of `full`:** 2 a precondition failed, nothing changed; 3 not enough disk; 5 application sessions still open, hold not run; 6 hold or dump failed its own check (including: the late-writer trap is not installed on all four tables); 7 guards not confirmed, api stopped again; 8 private records visible while the previous api was up, api stopped; 9 same, but the api **could not be stopped** (stop it by hand first).

**Late writers: what is prevented, what is only detected, what is not covered (read before approving the rollback)**
- **Prevented (confidentiality of internship-private records).** The hold transaction also installs the *late-writer trap*: a `BEFORE INSERT/UPDATE` trigger on the four tables (`ops_0107_park_*`, function `ops_0107_park_private`, `SECURITY DEFINER`, pinned `search_path`) that parks any row with an `internship_id` under the holding course and on the ledger **as it is written**. A private record written after the hold, by any writer (a 0107 api left running elsewhere, an application role, a person with `psql`), is never visible to the previous code. Shown on the real previous image: without the trap an independent enrolee was served `LATE PRIVATE …` records (rehearsal scenario 5, exit 9); with it, the same injection exits 0 and the record is hidden. The release drops the trap first, in the same transaction that puts the rows back, and checks that none is left.
- **Checked three more ways.** The hold refuses to finish (exit 6) unless all four triggers exist; `MODE=verify` FAILs if one is missing; a resumed `full` that finds the previous api running with a missing trap or a visible private record stops the api. After the previous api starts the visible-record count is taken again and a non-zero result stops the api (exit 8, or exit 9 if docker cannot confirm the stop).
- **Not prevented: other writes.** A stray 0107 api can still write every other kind of data (enrolments, payments, ...) while the previous code is live; the trap does not reject writes, it hides private ones. The cure for that is to make sure no 0107 api is running anywhere (one host: stop `erpx_api`, `celery_worker`, `celery_beat`; confirm `docker ps`), and, if you want it enforced, the lock-out below.
- **The zero-session check is still a snapshot** of `APP_DB_USER` connections only; sessions of other users and connections made after it are not seen. With the trap this no longer affects confidentiality; it affects only the integrity of non-private data written by an outside writer.
- **Trap limits:** a database superuser can drop it; a record parked by it is *hidden, not rejected*, so the writer believes the write succeeded (MODE=forward brings it back under its course). The trap function needs the tables to carry `internship_id` (revision 0107); it exists only between the hold and the release, so a later `alembic` run must not happen while it is installed.
- **Design decision, alternatives not chosen:** (a) *Filter in the guarded image*: the previous ORM models do not have `internship_id`; the four repositories' `get_by_id` and `list_for_course` and every id-based child route (questions, attempts, replies, results) would all need the filter, each replaced file pinned by hash; coverage would be hard to prove and any gap leaks. (b) *`ALTER ROLE erpx NOLOGIN` / `ALTER DATABASE erpx CONNECTION LIMIT 0`*: blocks all application writes, but changes database state that must be undone (role-wide `NOLOGIN` also blocks the role on other databases; the database-scoped limit does not, and superusers stay exempt); tested on a throw-away server, **not implemented, needs approval**. (c) *Maintenance mode at the web proxy*: needs a production Caddy change and does not stop a writer that talks to the database directly. The trap needs none of these and no production configuration beyond the hold itself.
- **Rehearsed on a real Docker daemon** (private daemon, synthetic data): see `REHEARSAL_REPORT_0107.md`. Still **not** exercised: the production compose `build:`, Caddy, S3 and systemd checks, `04_post_deploy_verify.sh`, production data volumes.

**After a rollback**, remember:
- Any later `docker compose up` of the api while on the old image **must** use the override: `docker compose -f docker-compose.prod.yml -f /opt/backups/pre-release/rollback-api-override.yml up -d --no-deps --no-build api`.
- Content created by the 0107 features is hidden, not deleted. The old screens have no Learning workspace.
- The previous release's other known gaps return too. The two cross-student reads (course results, course progress) are closed by the guarded image; confirm with `MODE=verify`.
- Uploaded curriculum files show a dead download link in the old UI (they are course-wide, so nothing leaks).

### 4.4 Roll forward
`90_rollback_code_only.sh MODE=forward` (stop the writers, release the hold, start the saved 0107 images, verify). The manual path: re-run `01` (with `EXPECT_REV_BEFORE=0107`; the migration is then a no-op), `02`, `03`, and only after the new api is running `MODE=release`, which refuses while the previous api is still running.

### 4.5 The two guards
`ops/release-0107/rollback_guard/results_routes.py` and `progress_routes.py` replace the previous release's route files inside the derived image. Rule for both: the caller is the student concerned, a superuser, or staff (results: grading / exam management permissions; progress: `lms.progress.manage`); everyone else gets 403; if the student record or permissions cannot be read the request fails and returns nothing. Both are embedded in `90_…` and a test keeps the embedded copies, hashes and SQL equal to the files; regenerate with `python ops/release-0107/wip/build_90_v2.py` after changing any of them.
The current (0107) progress route had the same gap and is fixed in the application as well (own / superuser / `lms.progress.manage`; `tests/api/test_lms_progress_access.py`), so a roll-forward does not bring it back.

---

## 5. Final sign-off
GO to deploy only if G1–G10 are all GO. GO to **declare the release good** only if `04` ends with `FAIL=0`, every row of 3.2 passed, and the baseline PDFs match. Anything else: part 4.

## 6. What was and was not verified (so you can weigh it)
**Verified by execution on copies:** the hold/release SQL (including idempotence, retention, and old-code behaviour with and without it), the crash-loop of the old image, the compose override, the preflight (read-only proven by the database refusing UPDATE/INSERT/DELETE/CREATE/DROP/TRUNCATE/ALTER and by PostgreSQL's own write counters unchanged; works on a 0106 schema), the verifier (fails when a table shrinks or a hold is active), the gates and dry-run output of 01–03, and the real code path of 01 (baselines, verified dump, env file, checkpoint SQL) against a scratch database.
**Not verified (needs the real host):** `docker compose build/up` on production, the S3 and systemd checks on the instance, real image names in the rollback env file, and anything that needs production data. Steps 01–03 reuse the commands of the 2026-10-30 release, which ran there.
