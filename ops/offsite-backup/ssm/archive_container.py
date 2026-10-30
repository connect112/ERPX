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


"""Archive the four approved in-app dumps to S3 before anything is removed from MinIO. Runs inside the erpx_api container.

Embedded in the SSM document pentrix-op-archive-old-dumps *after* delete_old_dumps.py, whose APPROVED table, MinioStore and
check() it uses (build_archive_doc.py joins the two; the tests do the same). It never deletes or changes anything in MinIO.

Modes (MODE environment variable):
  plan      read-only. Runs the same gates as the deletion (check()), reads three 16 MiB samples of each dump to estimate the
            compressed size and the monthly cost, and prints exactly which S3 keys would be written.
  stream    writes one dump, gzip-compressed, to stdout (the host pipes it to S3) and prints the checksums of the original bytes
            and of the compressed bytes to stderr as META|{json}. Exits 5 if the original bytes do not hash to the approved value.
  manifest  prints manifest.json: for each dump the job id, original filename, date, size, sha256, the S3 location, the
            compressed size and sha256, and the backup record as it was in the database.
  readme    prints README.txt (how to get a dump back).
  marker    prints VERIFIED.json from the results of the retrieval check made on the host. The deletion document refuses to run
            without it.
"""

import gzip
import hashlib
import io
import json
import os
import sys

BUCKET = "pentrix-erpx-backups-373384939117"
# Deliberately outside daily/ weekly/ monthly/: the bucket's lifecycle rules only expire those three prefixes, and the
# server's role can not delete or change lifecycle rules, so nothing under archive/ ever expires on its own.
S3_PREFIX = "archive/inapp-dumps-2026-10-08-to-11/"
MANIFEST_KEY = S3_PREFIX + "manifest.json"
README_KEY = S3_PREFIX + "README.txt"
VERIFIED_KEY = S3_PREFIX + "VERIFIED.json"
GZIP_LEVEL = 6                       # a plain gzip stream: any machine can read it with gunzip
SAMPLE_BYTES = 16 * 1024 * 1024      # three samples per dump: start, middle and end
PRICE_PER_GB_MONTH = 0.023           # S3 Standard, us-east-1


def archive_key(job_id, day):
    return f"{S3_PREFIX}{day}_{job_id}.sql.gz"


class _HashingSink:
    def __init__(self, out):
        self.out, self.sha, self.size = out, hashlib.sha256(), 0

    def write(self, data):
        self.sha.update(data)
        self.size += len(data)
        return self.out.write(data)

    def flush(self):
        self.out.flush()


def compress(chunks, out, limit=None):
    """Gzip the chunks into `out`, returning the sha256 and size of the original bytes and of the compressed bytes."""
    sink, original, original_size = _HashingSink(out), hashlib.sha256(), 0
    with gzip.GzipFile(fileobj=sink, mode="wb", compresslevel=GZIP_LEVEL, mtime=0, filename="") as stream:
        for chunk in chunks:
            if limit is not None and original_size >= limit:
                break
            original.update(chunk)
            original_size += len(chunk)
            stream.write(chunk)
    return {"original_sha256": original.hexdigest(), "original_size": original_size,
            "gz_sha256": sink.sha.hexdigest(), "gz_size": sink.size}


def estimate(store):
    """Compressed size and cost, from samples. Read-only."""
    rows = []
    for job_id, key, size, _sha, day in APPROVED:
        original = compressed = 0
        for offset in sorted({0, max(size // 2 - SAMPLE_BYTES // 2, 0), max(size - SAMPLE_BYTES, 0)}):
            meta = compress(store.chunks(key, offset, SAMPLE_BYTES), io.BytesIO(), limit=SAMPLE_BYTES)
            original, compressed = original + meta["original_size"], compressed + meta["gz_size"]
        ratio = compressed / max(original, 1)
        rows.append({"id": job_id, "day": day, "original_size": size, "ratio": ratio, "estimated_gz_size": int(size * ratio)})
    return rows, sum(r["estimated_gz_size"] for r in rows)


def monthly_cost(num_bytes):
    return num_bytes / 1024 ** 3 * PRICE_PER_GB_MONTH


RESTORE_STEPS = [
    "Download:   aws s3 cp s3://%s/<archive_object_key> - | gunzip > <original_filename>" % BUCKET,
    "Check:      sha256sum <original_filename>   (must equal original_sha256 in manifest.json)",
    "Load:       psql -d <empty database> -v ON_ERROR_STOP=1 -f <original_filename>   (plain SQL from pg_dump)",
    "Note:       these dumps were made by pg_dump 17 against PostgreSQL 16; psql 16 or newer loads them, and a `SET transaction_timeout` "
    "line may need removing for a server older than 17 (apps/api/scripts/restore_backup.py does this).",
]


def build_manifest(rows, metas, now):
    by_id = {row["id"]: row for row in rows}
    files = []
    for job_id, key, size, sha, day in APPROVED:
        meta = metas[job_id]
        if meta["original_sha256"] != sha or meta["original_size"] != size:
            raise ValueError(f"{job_id}: the archived bytes are not the approved original")
        files.append({
            "job_id": job_id, "original_filename": f"{job_id}.sql", "original_object_key": key, "backup_date": day,
            "original_size_bytes": size, "original_sha256": sha,
            "archive_object_key": archive_key(job_id, day), "archive_s3_uri": f"s3://{BUCKET}/{archive_key(job_id, day)}",
            "compression": f"gzip -{GZIP_LEVEL} (one gzip stream)",
            "archive_size_bytes": meta["gz_size"], "archive_sha256": meta["gz_sha256"],
            "backup_record_when_archived": by_id[job_id],
        })
    return {
        "purpose": "Recovery copies of the ERPX in-app database dumps of 8-11 October 2026, kept before their MinIO originals were removed.",
        "created_at": now, "source": "ERPX in-app backup: pg_dump (plain SQL) of the erpx database",
        "retention": "Permanent. Not covered by any lifecycle expiration rule; do not delete without the owner's written approval.",
        "how_to_restore": RESTORE_STEPS, "files": files,
    }


def build_marker(results, now):
    """results: {job_id: {"archive_size_ok": bool, "archive_sha256_ok": bool, "original_sha256_ok": bool}} from the retrieval check."""
    files, ok = [], True
    for job_id, key, size, sha, day in APPROVED:
        r = results.get(job_id, {})
        good = bool(r.get("archive_size_ok") and r.get("archive_sha256_ok") and r.get("original_sha256_ok"))
        ok = ok and good
        files.append({"job_id": job_id, "archive_object_key": archive_key(job_id, day), "original_sha256": sha,
                      "original_size_bytes": size, "verified": good, "archive_size_bytes": r.get("archive_size"),
                      "archive_sha256": r.get("archive_sha256")})
    return {"verified_at": now, "all_verified": ok,
            "method": "each archive was read back from S3, its size and sha256 checked against the manifest, then decompressed "
                      "and its sha256 checked against the original backup's approved sha256",
            "files": files}


def main():
    import datetime

    mode = os.environ.get("MODE", "plan")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if mode == "readme":
        print("ERPX in-app database dumps, 8-11 October 2026 (archived copies)\n")
        print("manifest.json lists every file: its original job id, name, date, size and sha256, where it is in S3, and the backup")
        print("record from the database. VERIFIED.json shows each copy was read back and matched.\n")
        print("\n".join(RESTORE_STEPS))
        return 0
    if mode == "manifest":
        print(json.dumps(build_manifest(json.loads(os.environ["DATA_JSON"])["rows"], json.loads(os.environ["METAS_JSON"]), now), indent=1))
        return 0
    if mode == "marker":
        print(json.dumps(build_marker(json.loads(os.environ["RESULTS_JSON"]), now), indent=1))
        return 0
    store = MinioStore()
    if mode == "stream":
        key = sys.argv[1]
        wanted = {a[1]: a for a in APPROVED}
        if key not in wanted:
            print("ABORT: not one of the approved keys", file=sys.stderr)
            return 2
        meta = compress(store.chunks(key), sys.stdout.buffer)
        sys.stdout.buffer.flush()
        print("META|" + json.dumps(meta), file=sys.stderr)
        return 0 if (meta["original_sha256"], meta["original_size"]) == (wanted[key][3], wanted[key][2]) else 5
    if mode != "plan":
        print(f"ABORT: unknown mode {mode!r}")
        return 2
    data = json.loads(os.environ["DATA_JSON"])
    problems, actions = check(data["rows"], data["newest"], store)
    if problems:
        print("ABORT: nothing was changed. Problems:")
        for problem in problems:
            print(" -", problem)
        return 2
    print("all gates passed: the four originals match their approved sizes and checksums; the three newest backups are present")
    rows, total = estimate(store)
    for row in rows:
        print(f"  {row['day']} {row['id']}: {row['original_size']:,} bytes -> about {row['estimated_gz_size']:,} bytes "
              f"(ratio {row['ratio']:.2f}, from samples)")
    print(f"estimated archive size: {total:,} bytes ({total / 1024 ** 3:.2f} GiB) = about US${monthly_cost(total):.3f} a month "
          f"(upper bound if nothing compressed: US${monthly_cost(sum(a[2] for a in APPROVED)):.3f})")
    print("S3 keys that archive mode would write:")
    for _id, _key, _size, _sha, day in APPROVED:
        print("  " + archive_key(_id, day))
    print("  " + MANIFEST_KEY, "\n  " + README_KEY, "\n  " + VERIFIED_KEY + "  (after verify mode)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
