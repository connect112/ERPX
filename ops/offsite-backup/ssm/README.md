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
3. Facts are read from the database, then `delete_old_dumps.check` verifies, reading only:
   - the MinIO bucket is not versioned (otherwise deleting would not free space; it stops and asks);
   - the three newest completed backups (30, 29 and 28 Oct) are newer than all four, are not among them, and their files exist with
     the recorded size;
   - each of the four has a completed record equal to the table above (id, key, size, sha256), its file has the approved size, and
     a freshly recomputed sha256 equals the approved and the recorded one.
4. Only then, in delete mode: each object is removed, confirmed gone, then the next. The four record updates run afterwards in
   one database transaction.

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
- **If that matters**, archive first: compress each dump and copy it to S3 under a prefix with no expiry (a few hundred MB each,
  about US$0.1 a month). It is not part of this document; ask for it before running `delete`.
- The checksums and sizes of all four are already recorded here, in the database and in the verification output.

## Post-cleanup checks (printed by the document)

The four records show `file_pointer_cleared = true`; the four newest records are still there; a second verify pass reports all four
as already removed and the newest three present; disk space; running and unhealthy container counts; `/api/v1/health`.

## Registering and running it (after approval)

1. Account owner: Systems Manager > Documents > Create document > Command, name `pentrix-op-delete-old-dumps`, paste the JSON.
2. Run it from Run Command, target instance `i-0054474b85332980a`, `Mode=verify`, and read the output.
3. Only if the owner approves: run again with `Mode=delete` and `Confirm=DELETE-4-OLD-DUMPS`.
   Running it yourself in the console needs no extra permission for `pentrix-ops-readonly`, which deliberately cannot do this.
