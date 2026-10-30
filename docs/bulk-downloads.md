# Bulk downloads

One service (`modules/bulk_exports`) lets staff download many generated or stored documents as one ZIP, with file and
folder names they choose. Every module plugs in through a small adapter; the job, ZIP, naming rules, screens, expiry and
audit are shared.

## Supported documents

| Source key | What | Where the button is | Permission (same as the single download) | How the bytes are produced |
|---|---|---|---|---|
| `exam_certificates` | Certificates of one workshop exam: workshop and exam certificates, a hackathon award's certificates, or one internship certificate exam | Workshop exam → Live → **Download certificates** | `workshops.view`, or an active instructor of the exam's internship | `render_certificate` (the function the review preview and the email use), with the issued number and name fix |
| `internship_certificates` | An internship's participation **and** completion certificates together | Internship → Certificates → **Download issued certificates** | `our_internships.view`, or an active instructor | as above |
| `offer_letters` | An internship's current generated offer letters (generated, approved or released) | Internship → Offer letters → **Bulk download (custom names)** | `our_internships.view`, or an active instructor | stored PDF copied byte for byte |
| `payslips` | The payslips of one payroll run | Payroll run → **Download payslips** | `payroll.runs.view` | `PayrollService.get_payslip_pdf` |
| `documents` | Files uploaded through Documents for one record | Documents panel → **Download all** | `documents.view` | object copied byte for byte from storage |

Not included, because no document file exists for them: LMS course certificates (`lms_certificates`) and Pentrix
certifications are records with a number only; there is no PDF to download. When a PDF is added for them, they become
a new `DocumentSource`.

Only documents that already exist are offered. A certificate that has not been issued (no certificate number) is not
listed, and an export never assigns numbers, sends email or changes a document.

## Using it

1. **Choose documents.** Search and filter; ticks are kept across pages. Ticking a whole page offers **Choose all N that
   match**, which selects everything matching the filters (minus anything unticked afterwards) without sending every id.
2. **Name the files.** Pick a preset or type a format; click a placeholder to insert it at the cursor. Purple
   placeholders come from the module's own fields (an exam's registration questions such as `{{registration_id}}`,
   imported student columns such as `{{registration_number}}`). Choose folders (none, a preset, or a custom
   `{{a}}/{{b}}` format) and the ZIP name. The preview on the right is produced by the server with the real rules.
3. **Prepare ZIP.** Up to `BULK_EXPORT_INLINE_MAX_ITEMS` documents are zipped straight away; more go to the Celery
   worker and the dialog shows progress. Failed documents are listed on screen and in `_failed_documents.txt` inside the
   ZIP; the others are still included.
4. **Download.** The button asks the API for a link signed for `BULK_EXPORT_LINK_MINUTES`; the browser fetches the ZIP
   straight from storage. **Administration → Bulk Downloads** lists your downloads with progress, failures, download and
   remove.

## Naming rules (`modules/bulk_exports/filenames.py`)

- Placeholders are `{{key}}` (lower case, digits, underscore). Any placeholder the source does not offer is refused
  before the job starts, with its name in the message.
- Always available: `{{document_type}}`, `{{index}}` (zero-padded position), `{{export_date}}`. ZIP name:
  `{{scope_name}}`, `{{document_type}}`, `{{export_date}}`, `{{count}}`.
- Extension: the document's real one. A format may end in it or leave it off; any other extension (`.exe`, `.docx` for
  a PDF) is refused. Uploaded documents keep their own extension, so a typed one is refused there.
- Values cannot create paths: `/ \ : * ? " < > |`, control characters and `..` are removed from values; folder formats
  are at most three plain levels, never absolute, never `..`. Windows reserved names (`CON`, `NUL`, ...) get `_`.
- Missing values leave no doubled or dangling separators; a name with nothing left becomes `<document type>_<index>`.
  The preview warns how many documents are missing each value.
- Names and paths are length-capped; duplicates (compared ignoring case) get `_2`, `_3`, ...

## Security

- Every endpoint needs a signed-in user and applies the module's own permission; the scope (exam, internship, run) is
  loaded inside the caller's organization, so another organization's scope is "not found".
- The list of document ids is fixed when the job is created, after the permission check. The worker checks the
  permission again as the same user, and loads only those ids that are still in that scope and organization; ids
  smuggled in from elsewhere are dropped.
- Jobs, links and files are visible only to the person who asked; to anyone else they do not exist (404). Before a
  link is issued, the permission is checked again, so someone who lost access cannot collect a file prepared earlier.
- ZIPs are written to a temporary local file (deleted in all cases) and stored under `bulk-exports/<org>/<job>.zip`.
  Links are short-lived. The clean-up task (Celery beat `bulk-exports-cleanup`, every 30 min) removes ZIPs past
  `expires_at` and ends jobs a stopped worker left behind (> 2 h). The Storage Manager lists these ZIPs as protected.
- Audit: the job row goes through the normal audit hooks: creation (who, what, which scope, naming options), status
  changes and each download link handed out. The id list and progress counters are excluded from the audit trail.
- Limits: documents per ZIP, total bytes, and jobs running at once per user (below); job creation is rate-limited
  (20/min).

## Configuration (environment, all optional)

| Setting | Default | Meaning |
|---|---|---|
| `BULK_EXPORT_RETENTION_HOURS` | 24 | How long a finished ZIP is kept |
| `BULK_EXPORT_LINK_MINUTES` | 5 | Validity of a download link |
| `BULK_EXPORT_MAX_ITEMS` | 5000 | Documents per download |
| `BULK_EXPORT_MAX_BYTES` | 2 GiB | Total size of the documents in one ZIP |
| `BULK_EXPORT_INLINE_MAX_ITEMS` | 20 | Up to this many are zipped in the request; more go to Celery |
| `BULK_EXPORT_MAX_ACTIVE_PER_USER` | 3 | Downloads one person can have queued or running |

The worker needs local temporary space for the largest ZIP it builds (see `BULK_EXPORT_MAX_BYTES`); the production host
has about 8.6 GB free.

## Deployment notes

- Migration `0097_bulk_export_jobs` adds one table; downgrade drops it. No existing table changes.
- The API, `celery_worker` (new task module) and `celery_beat` (new schedule entry) all need the new image; `web` for
  the screens. No new environment variables are required.

## Adding a module

Write a `DocumentSource` (`modules/bulk_exports/sources/base.py`): `open_scope` (load the scope in the organization and
apply the module's permission), `query` (the existing documents, no bytes), `fetch` (the bytes, using the module's own
download code), plus placeholders and presets. Register it in `sources/__init__.py`, add tests, and put a
`<BulkDownloadButton source="..." scopeId={...} />` on the module's page.
