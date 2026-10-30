# SSM documents and IAM policies for backup verification and the old-dump cleanup

Nothing in this folder is registered with AWS or has been run in its deletion form. Registering a document needs someone with
`ssm:CreateDocument` (the account owner); running it is a separate act.

| File | Kind | Changes anything? |
|---|---|---|
| `pentrix-ro-backup-health.json` | SSM command document | No (read-only) |
| `pentrix-ro-old-backups.json` | SSM command document | No (read-only; writes and removes one tiny temp file) |
| `pentrix-op-delete-old-dumps.json` | SSM command document, built by `build_delete_doc.py` from `delete_old_dumps.py` | **Only with `Mode=delete` and the confirmation phrase** |
| `iam-policy-A-ops-readonly-aws.json` | IAM, `pentrix-ops-readonly` | No: read-only S3, one role, simulation, EC2 describe |
| `iam-policy-B-run-fixed-documents.json` | IAM, attach only while needed | Lets the user run `pentrix-ro-*` documents on the ERPX server |

## `pentrix-op-delete-old-dumps`: what it does

It removes exactly four in-app database dumps from MinIO and clears the pointer in their records. Their ids, keys, sizes and sha256
are written into the code (the owner approved them on 30 Oct 2026 after read-only verification):

| Date | Job id and object key | Size (bytes) | SHA-256 |
|---|---|---|---|
| 8 Oct | `60b5ddc6-ab6d-4dcb-a36b-9085908d5589`<br>`backups/60b5ddc6-ab6d-4dcb-a36b-9085908d5589.sql` | 1,183,191,170 | `979adc444c5914d569552c9564d783cf29c03cc7a6a90ad674022451b698ffdd` |
| 9 Oct | `6d502c1b-d465-4690-848e-6b161f0099a1`<br>`backups/6d502c1b-d465-4690-848e-6b161f0099a1.sql` | 1,183,203,261 | `18c9da67fbdb15e887ceacfa458545ee29d9d4511869d9f3c2fd1ff9e215ecf0` |
| 10 Oct | `6b693aff-1ca9-4d19-851d-1e585c63b0de`<br>`backups/6b693aff-1ca9-4d19-851d-1e585c63b0de.sql` | 1,202,157,127 | `fcdc7fa820aa98dbe3c7ecaf89c9c21323e44ef87e8ad7e9db674991b1ca503c` |
| 11 Oct | `aec2d1b7-6673-4674-86c9-1832afe0db6b`<br>`backups/aec2d1b7-6673-4674-86c9-1832afe0db6b.sql` | 1,202,404,108 | `48f01a16bb2ad3e66b26e83506eeb9468d8aceaedc086861d41b784e9dac7fd7` |

Total 4,770,955,666 bytes (4,550 MB, about 4.44 GiB). Nothing else can be passed to the delete call.

**Parameters.** `Mode` is `verify` (default, changes nothing) or `delete`. `Confirm` must be exactly `DELETE-4-OLD-DUMPS` for `delete`.
Run `verify` first; it is the rehearsal and prints what `delete` would do.

**Gates, in order. Any failure stops the run before anything is changed.**
1. Confirmation phrase (delete mode only).
2. The off-server backup is green: `last_status.json` says ok, is under 28 hours old, and that day's S3 folder has `SHA256SUMS`.
   2b. **The four archive copies exist in S3 and were verified by reading them back:** `VERIFIED.json` must say all four are verified, name exactly
       the four approved dumps with their approved sha256, and each S3 object must still be the verified size.
3. Facts are read from the database, then `delete_old_dumps.check` verifies, reading only:
   - the MinIO bucket is not versioned (otherwise deleting would not free space; it stops and asks);
   - the three newest completed backups (30, 29 and 28 Oct) are newer than all four, are not among them, and their files exist with
     the recorded size;
   - each of the four has a completed record equal to the table above (id, key, size, sha256), its file has the approved size, and
     a freshly recomputed sha256 equals the approved and the recorded one.
4. Only then, in delete mode: each object is removed, confirmed gone, then the next. The four record updates run afterwards in
   one database transaction.
   The document then checks that all four records really were updated and stops with an error if not (a second run finishes the records and touches no file).

**What happens to the records.** Not deleted. Each keeps its id, dates, size and sha256 as history. `storage_key` becomes empty
(the column allows it) and `error_message` gets a note: "File removed on <date> after verification; it was backups/<id>.sql (sha256 ...)".
The admin "download" link for those four then reports that no completed backup file exists, which is true.

**Safe to run again.** A finished job is recognised and skipped. If a run stops after removing a file but before updating its record,
the next run finishes that record only.

**What it does not touch.** Every other object under `backups/` (including the 28, 29 and 30 Oct dumps), every other MinIO object, any
database table except those four `backup_jobs` rows, any service (nothing restarts), and the off-server S3 backups.

## Recovery assessment

- **Deleting is permanent.** The MinIO bucket has no versioning or Trash, so there is no undo.
- **What is lost:** the ability to restore the database as it was on 8, 9, 10 or 11 October. The data that still exists today is in
  the 28, 29 and 30 Oct dumps and the S3 backups (the S3 daily copies only start on 29 Oct, and its lifecycle keeps 14 days).
  Anything that was deleted from the database between 8 and 28 Oct could only be recovered from these four.
- **The archive removes that loss.** `pentrix-op-archive-old-dumps` (below) keeps a verified, compressed copy of each dump in S3 with
  no expiry, and the deletion document refuses to run until those copies have been read back and matched.
- The checksums and sizes of all four are already recorded here, in the database and in the verification output.

## Post-cleanup checks (printed by the document)

The four records show `file_pointer_cleared = true`; the four newest records are still there; a second verify pass reports all four
as already removed and the newest three present; disk space; running and unhealthy container counts; `/api/v1/health`.

## `pentrix-op-archive-old-dumps`: keep the four dumps in S3 first

Built by `build_archive_doc.py` from `archive_old_dumps.py` (runs in the container) and `archive_host.sh` (runs on the host).
It never deletes or changes anything in MinIO, and the server's S3 role cannot delete, so it can only add objects.

| `Mode` | What it does | Writes |
|---|---|---|
| `plan` (default) | Runs the same gates as the deletion (originals match their approved size and checksum; newest three present; bucket unversioned; off-server backup green), reads three 16 MiB samples of each dump to **estimate the compressed size and the monthly cost**, and lists the exact S3 keys | nothing |
| `archive` (needs `Confirm=ARCHIVE-4-OLD-DUMPS`) | Streams each dump from MinIO through gzip straight to S3, with no temporary file on the host's disk. It hashes the original bytes while reading (they must equal the approved sha256) and the compressed bytes, then writes `manifest.json` and `README.txt` | four `.sql.gz`, the manifest, README |
| `verify` | Reads every archive back **from S3**, checks its size and sha256 against the manifest, decompresses it and checks the sha256 of the result against the original approved sha256, then writes `VERIFIED.json` only if all four match | `VERIFIED.json` |

**Where.** `s3://pentrix-erpx-backups-373384939117/archive/inapp-dumps-2026-10-08-to-11/` in the existing private, encrypted, versioned
bucket: `<date>_<job id>.sql.gz` ×4, `manifest.json`, `README.txt`, `VERIFIED.json`. Standard gzip, so any machine can restore with
`aws s3 cp ... - | gunzip > file.sql`.

**Recovery information kept in `manifest.json`** for each dump: job id, original filename (`<id>.sql`) and object key, backup date,
original size and sha256, the S3 location, compression used, the archive's size and sha256, and the full `backup_jobs` record as it was
when archived. It also says how to restore.

**It cannot expire.** The bucket's lifecycle rules only expire `daily/`, `weekly/` and `monthly/`; nothing matches `archive/`
(`test_no_lifecycle_rule_can_expire_anything_under_the_archive_prefix` fails if someone adds a rule that does), and the server's role is
denied delete and lifecycle changes. Removing the archive would need the owner to act with their own AWS access.

**Cost.** S3 Standard, us-east-1, US$0.023 per GB-month. Transfer inside the region is free, and the read-back runs on the server, so
there is no retrieval or data-transfer charge.

| Compression of the SQL text | Archive size | Per month |
|---|---|---|
| 8x (typical for plain SQL) | about 0.6 GB | about US$0.014 |
| 3x (pessimistic) | about 1.6 GB | about US$0.037 |
| none (impossible worst case) | 4.77 GB | US$0.102 |

`Mode=plan` replaces this table with a figure measured from the real dumps before anything is written. A second, independent check on another
machine (download, decompress, hash) would cost one-off data transfer of about US$0.05 to 0.14; it is optional.

**Does not need new AWS permissions.** It uses the instance role's existing put and get on the bucket; nothing is attached to anyone.

## Order of operations (each step after the first needs the owner's approval)

1. Account owner registers the two documents (Systems Manager > Documents > Create document > Command, paste each JSON).
2. Run `pentrix-op-archive-old-dumps` with `Mode=plan` and read the estimate. Nothing is written.
3. Run it with `Mode=archive` and `Confirm=ARCHIVE-4-OLD-DUMPS`; then `Mode=verify`.
4. The assistant shows the final deletion manifest (the table above plus the archive locations and sizes from `manifest.json`) for separate approval.
5. Run `pentrix-op-delete-old-dumps` with `Mode=verify`, read it; then, only if approved, `Mode=delete` with `Confirm=DELETE-4-OLD-DUMPS`.

Running a document in the console needs no extra permission for `pentrix-ops-readonly`, which deliberately cannot do any of this.

## How it was rehearsed

Besides the unit tests, both documents were run end to end on a development machine with synthetic dumps: the real shell commands under
bash, the real container Python, the real AWS CLI against a scratch MinIO bucket standing in for S3, and a scratch database standing in
for `backup_jobs`. 25 checks passed, including: plan writes nothing; archive refuses without its phrase; archive is idempotent; verify
reads back and writes the marker; a corrupted archive makes verify fail and the deletion refuse; the deletion refuses without a verified
archive, without its phrase, and with a stale off-server backup; delete removes exactly the four originals, leaves the newest three,
clears the four pointers and keeps the sha256; and running it again changes nothing. The rehearsal found a real bug (the record update ran
`docker exec` without `-i`, so it silently did nothing) that the unit tests could not.
