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
| `sql/rollback_hold.sql`, `sql/rollback_release.sql` | the two statements sets embedded in `90_…` | yes (rollback) |

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
If the **migration itself failed**, the database is still at the old revision (it runs in one transaction): use `MODE=images` only, no hold needed.

**Never run `alembic downgrade 0106`**: it drops the question rows, attempt answers, cohort scoping and upload metadata created since the release, and orphans uploaded files.
A restore of the pre-release dump is the last resort, needs its own approval, and loses everything written since the dump.

### 4.2 Why a plain image swap is unsafe (both proven in rehearsal, on real rows)
1. **Private content would be exposed.** The previous code lists assessments, discussion threads, practicals and vivas by course alone, and every student may list them. With old code on the 0107 schema, an independent enrolee saw `PRIVATE Quiz`, `PRIVATE thread`, `PRIVATE practical`, `PRIVATE viva`.
2. **The previous api would crash-loop.** Its entrypoint runs `alembic upgrade head` (`RUN_MIGRATIONS=true`) and alembic stops with `Can't locate revision identified by '0107'`.

### 4.3 The procedure
```text
90_rollback_code_only.sh   with MODE=full on its first line     (run it once with DRY_RUN=1 to read the plan)
```
In order: (1) a small safety dump of the four tables → (2) **hold**: every internship-private row is moved, unchanged, under a soft-deleted holding course of the same organization (the previous code treats a deleted course as "not found"); the move
is recorded row by row in `ops_0107_rollback_hold`, and the transaction checks that nothing private remains under a visible course or rolls back → (3) restore the six saved images, the api first, with `RUN_MIGRATIONS=false` through
`/opt/backups/pre-release/rollback-api-override.yml` → (4) read-only verification. The database stays at 0107; nothing is dropped or deleted.

**Rehearsed result (old code, 0107 schema, real rows):** with the hold, an independent enrolee and a cohort student see only the course-wide items; opening the holding course returns 403/404; another student's private marks are not returned.
Every table keeps its row count; the held rows differ from the originals only in `course_id`; a second hold is a no-op; after the release every table is **byte-identical** to before (verified by content hashes, through two full cycles).

**After a rollback**, remember:
- Any later `docker compose up` of the api while on the old image **must** use the override: `docker compose -f docker-compose.prod.yml -f /opt/backups/pre-release/rollback-api-override.yml up -d --no-deps --no-build api`.
- Content created by the 0107 features is hidden, not deleted. The old screens have no Learning workspace.
- The rollback also brings back behaviour that exists in production today and that this PR fixes (seen in the rehearsal: any student can read another student's combined course results through the old results route). The previous release's other known gaps return too.
- Uploaded curriculum files show a dead download link in the old UI (they are course-wide, so nothing leaks).

### 4.4 Roll forward
Re-run `01` (with `EXPECT_REV_BEFORE=0107`; the migration is then a no-op), `02`, `03`, and only after the new api is running: `90_rollback_code_only.sh MODE=release`. It refuses while the previous api is still running (that would re-expose the records) and puts each row back under its original course.

---

## 5. Final sign-off
GO to deploy only if G1–G10 are all GO. GO to **declare the release good** only if `04` ends with `FAIL=0`, every row of 3.2 passed, and the baseline PDFs match. Anything else: part 4.

## 6. What was and was not verified (so you can weigh it)
**Verified by execution on copies:** the hold/release SQL (including idempotence, retention, and old-code behaviour with and without it), the crash-loop of the old image, the compose override, the preflight (read-only proven by the database refusing UPDATE/INSERT/DELETE/CREATE/DROP/TRUNCATE/ALTER and by PostgreSQL's own write counters unchanged; works on a 0106 schema), the verifier (fails when a table shrinks or a hold is active), the gates and dry-run output of 01–03, and the real code path of 01 (baselines, verified dump, env file, checkpoint SQL) against a scratch database.
**Not verified (needs the real host):** `docker compose build/up` on production, the S3 and systemd checks on the instance, real image names in the rollback env file, and anything that needs production data. Steps 01–03 reuse the commands of the 2026-10-30 release, which ran there.
