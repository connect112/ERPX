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
