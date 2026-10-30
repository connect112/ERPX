"""Remove exactly four verified in-app database dumps (8-11 October 2026) from MinIO. Runs inside the erpx_api container.

This is the code embedded in the SSM document pentrix-op-delete-old-dumps (see build_delete_doc.py). It is written as small
functions so tests/unit/test_delete_old_dumps.py can run every decision against a fake MinIO.

How it stays safe:
  * Only the four APPROVED backups can ever be touched. Their ids, object keys, sizes and sha256 are written in this file.
  * check() only reads. It aborts, listing every problem, unless ALL of these hold: the bucket is not versioned (so a delete
    really frees the space); the three newest completed backups are newer than the four, are not among them, and their files
    exist with the recorded size; each of the four has a completed record that matches the approved values, and its file in
    MinIO has the approved size and a freshly recomputed sha256 equal to the approved and recorded one.
  * MODE=verify (the default) never changes anything. Deleting needs MODE=delete.
  * Deletion removes one object, confirms it is gone, then moves to the next. Records are changed afterwards by the caller
    in one database transaction. It can be run again: a finished job is recognised and skipped.
  * Nothing outside the four keys, and nothing outside backups/, is ever passed to the delete call.
"""

import datetime
import hashlib
import json
import os
import sys

# id, object key, size in bytes, sha256, day of the backup. Approved by the owner after read-only verification (30 Oct 2026).
APPROVED = (
    ("60b5ddc6-ab6d-4dcb-a36b-9085908d5589", "backups/60b5ddc6-ab6d-4dcb-a36b-9085908d5589.sql", 1183191170,
     "979adc444c5914d569552c9564d783cf29c03cc7a6a90ad674022451b698ffdd", "2026-10-08"),
    ("6d502c1b-d465-4690-848e-6b161f0099a1", "backups/6d502c1b-d465-4690-848e-6b161f0099a1.sql", 1183203261,
     "18c9da67fbdb15e887ceacfa458545ee29d9d4511869d9f3c2fd1ff9e215ecf0", "2026-10-09"),
    ("6b693aff-1ca9-4d19-851d-1e585c63b0de", "backups/6b693aff-1ca9-4d19-851d-1e585c63b0de.sql", 1202157127,
     "fcdc7fa820aa98dbe3c7ecaf89c9c21323e44ef87e8ad7e9db674991b1ca503c", "2026-10-10"),
    ("aec2d1b7-6673-4674-86c9-1832afe0db6b", "backups/aec2d1b7-6673-4674-86c9-1832afe0db6b.sql", 1202404108,
     "48f01a16bb2ad3e66b26e83506eeb9468d8aceaedc086861d41b784e9dac7fd7", "2026-10-11"),
)
KEEP_NEWEST = 3
LATEST_APPROVED_DAY = max(day for *_, day in APPROVED)


class MinioStore:
    """The real bucket. Only these calls exist, so there is no way to list anything, or delete anything but a key passed to remove()."""

    def __init__(self):
        # The container's own environment (the same variables the application reads). Importing the application's settings
        # module here would load much of the app just to read these, which matters on a host with little free memory.
        from minio import Minio

        self.bucket = os.environ.get("MINIO_BUCKET", "erpx-storage")      # the application's default bucket
        self.client = Minio(os.environ["MINIO_ENDPOINT"], access_key=os.environ["MINIO_ACCESS_KEY"],
                            secret_key=os.environ["MINIO_SECRET_KEY"],
                            secure=os.environ.get("MINIO_SECURE", "false").strip().lower() in ("1", "true", "yes"))

    def versioning(self):
        return (self.client.get_bucket_versioning(self.bucket).status or "").strip()

    def size(self, key):
        """Size in bytes, or None if there is no such object."""
        from minio.error import S3Error

        try:
            return self.client.stat_object(self.bucket, key).size
        except S3Error as exc:
            if exc.code in ("NoSuchKey", "NoSuchObject"):
                return None
            raise

    def sha256(self, key):
        digest = hashlib.sha256()
        response = self.client.get_object(self.bucket, key)
        try:
            for chunk in response.stream(1024 * 1024):
                digest.update(chunk)
        finally:
            response.close()
            response.release_conn()
        return digest.hexdigest()

    def chunks(self, key, offset=0, length=0):
        """Read-only stream of the object (or a byte range of it), 1 MiB at a time. length 0 means to the end."""
        response = self.client.get_object(self.bucket, key, offset=offset, length=length)
        try:
            yield from response.stream(1024 * 1024)
        finally:
            response.close()
            response.release_conn()

    def remove(self, key):
        self.client.remove_object(self.bucket, key)


def check(db_rows, newest_rows, store):
    """Read-only. Returns (problems, actions); actions is empty unless there are no problems.

    db_rows: the records for the four approved ids. newest_rows: the three newest completed backups."""
    problems = []

    state = store.versioning()
    if state not in ("", "Off"):
        problems.append(f"the bucket's versioning is '{state}', so deleting would not free the space; stop and ask")

    approved_ids = {a[0] for a in APPROVED}
    if len(newest_rows) != KEEP_NEWEST:
        problems.append(f"expected the {KEEP_NEWEST} newest completed backups, found {len(newest_rows)}")
    for row in newest_rows:
        label = f"newest backup {row['id']}"
        if row["id"] in approved_ids:
            problems.append(f"{label} is one of the four to delete")
        if str(row["started_at"])[:10] <= LATEST_APPROVED_DAY:
            problems.append(f"{label} ({str(row['started_at'])[:10]}) is not newer than the approved backups")
        if row["status"] != "completed" or not row["storage_key"]:
            problems.append(f"{label} is not a completed backup with a stored file")
            continue
        on_disk = store.size(row["storage_key"])
        if on_disk is None:
            problems.append(f"{label}: its file {row['storage_key']} is missing")
        elif on_disk != row["size_bytes"]:
            problems.append(f"{label}: its file is {on_disk} bytes but the record says {row['size_bytes']}")

    by_id = {row["id"]: row for row in db_rows}
    extra = set(by_id) - approved_ids
    if extra:
        problems.append(f"unexpected records returned: {sorted(extra)}")

    actions = []
    for job_id, key, size, sha, day in APPROVED:
        label = f"{day} backup {job_id}"
        row = by_id.get(job_id)
        if row is None:
            problems.append(f"{label}: no record found")
            continue
        on_disk = store.size(key)
        if on_disk is None and row["storage_key"] is None:
            actions.append({"id": job_id, "key": key, "sha256": sha, "state": "done"})
            continue
        if on_disk is None:
            # the file is already gone but the record still points at it (an earlier run stopped half way)
            if row["storage_key"] != key:
                problems.append(f"{label}: file missing and the record points at {row['storage_key']!r}, not {key}")
            else:
                actions.append({"id": job_id, "key": key, "sha256": sha, "state": "record_only"})
            continue
        if row["storage_key"] is None:
            problems.append(f"{label}: the file still exists but the record no longer points at it")
            continue
        mismatches = []
        if row["status"] != "completed":
            mismatches.append(f"status is {row['status']!r}")
        if row["storage_key"] != key:
            mismatches.append(f"record points at {row['storage_key']!r}")
        if row["size_bytes"] != size:
            mismatches.append(f"recorded size {row['size_bytes']} is not the approved {size}")
        if row["sha256"] != sha:
            mismatches.append("recorded sha256 is not the approved one")
        if on_disk != size:
            mismatches.append(f"the file is {on_disk} bytes, not the approved {size}")
        if mismatches:
            problems.append(f"{label}: " + "; ".join(mismatches))
            continue
        recomputed = store.sha256(key)
        if recomputed != sha:
            problems.append(f"{label}: recomputed sha256 {recomputed} is not the approved {sha}")
            continue
        actions.append({"id": job_id, "key": key, "sha256": sha, "state": "delete"})

    return problems, ([] if problems else actions)


def record_sql(action, today):
    """The one statement that clears a backup's pointer to its file. The record itself, with its size and checksum, stays."""
    note = f"File removed on {today} after verification; it was {action['key']} (sha256 {action['sha256']})."
    return (f"update backup_jobs set storage_key = null, error_message = '{note}' where id = '{action['id']}' "
            f"and status = 'completed' and sha256 = '{action['sha256']}' and storage_key = '{action['key']}';")


def apply(actions, store, delete, today):
    """With delete=False nothing changes. With delete=True: remove each approved object, confirm it is gone, and return the
    SQL for the records. Keys come only from APPROVED, and each must be under backups/."""
    sql = []
    for action in actions:
        if action["state"] == "delete" and delete:
            assert action["key"].startswith("backups/") and action["key"] in {a[1] for a in APPROVED}
            store.remove(action["key"])
            if store.size(action["key"]) is not None:
                raise RuntimeError(f"{action['key']} is still there after the delete call; stopping")
            print(f"removed {action['key']}", flush=True)
        if action["state"] in ("delete", "record_only") and delete:
            sql.append(record_sql(action, today))
    return sql


def main():
    mode = os.environ.get("MODE", "verify")
    if mode not in ("verify", "delete"):
        print(f"ABORT: unknown mode {mode!r}")
        return 2
    data = json.loads(os.environ["DATA_JSON"])
    store = MinioStore()
    problems, actions = check(data["rows"], data["newest"], store)
    if problems:
        print("ABORT: nothing was changed. Problems:")
        for problem in problems:
            print(" -", problem)
        return 2
    counts = {state: sum(1 for a in actions if a["state"] == state) for state in ("delete", "record_only", "done")}
    freed = sum(a_size for (_, key, a_size, _, _) in APPROVED if any(x["key"] == key and x["state"] == "delete" for x in actions))
    print(f"all checks passed: {counts['delete']} to delete ({freed} bytes), {counts['record_only']} record-only, "
          f"{counts['done']} already done; the {KEEP_NEWEST} newest backups are present and untouched")
    if mode == "verify":
        print("verify mode: nothing was changed")
        return 0
    for line in apply(actions, store, True, datetime.date.today().isoformat()):
        print("SQL|" + line)
    print(f"RESULT removed={counts['delete']} record_only={counts['record_only']} already_done={counts['done']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
