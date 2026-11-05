#!/usr/bin/env python3
"""READ-ONLY inventory of database backup files: which format each is, which pg_dump made it, and what can restore it.

It reads at most the first 8 KiB of every file (or object), writes nothing, and needs no PostgreSQL tools. Two sources:

  --files PATH [PATH ...]          local files (for example headers fetched with `aws s3api get-object --range bytes=0-8191`)
  --minio-prefix backups/          objects in the application's MinIO bucket, read with a ranged GET. Run it inside the API
                                   container, which already has the MinIO client and its settings:
                                   docker exec -i erpx_api python - --minio-prefix backups/ < backup_inventory.py

It cannot prove a backup is restorable: a 8 KiB header says nothing about the rest of the file. The restore rehearsal in
docs/operations/backup-format-inventory.md is what proves that, on a non-production machine.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys

HEADER_BYTES = 8192
MAGIC = b"PGDMP"

# archive version -> the PostgreSQL release that introduced it (for the "needs pg_restore >=" column)
_ARCHIVE_VERSION_MIN_CLIENT = {(1, 14): 12, (1, 15): 16, (1, 16): 17}


class _Reader:
    def __init__(self, data: bytes):
        self.data, self.pos = data, 0

    def byte(self) -> int:
        if self.pos >= len(self.data):
            raise EOFError("header is longer than the bytes read")
        b = self.data[self.pos]
        self.pos += 1
        return b

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise EOFError("header is longer than the bytes read")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def integer(self, int_size: int) -> int:
        sign = self.byte()
        value = int.from_bytes(self.take(int_size), "little")
        return -value if sign else value

    def string(self, int_size: int) -> str | None:
        n = self.integer(int_size)
        return None if n < 0 else self.take(n).decode("utf-8", errors="replace")


def parse_custom_header(data: bytes) -> dict:
    """The header of a pg_dump custom-format (-Fc) archive: version, who dumped it, from which server. Mirrors ReadHead() in
    PostgreSQL's pg_backup_archiver.c for archive versions 1.14 to 1.16 (PostgreSQL 12 to 18)."""
    if data[:5] != MAGIC:
        raise ValueError("not a custom-format archive")
    r = _Reader(data)
    r.take(5)
    vmaj, vmin = r.byte(), r.byte()
    vrev = r.byte() if (vmaj > 1 or (vmaj == 1 and vmin > 0)) else 0
    int_size = r.byte()
    off_size = r.byte() if (vmaj, vmin) >= (1, 7) else int_size
    fmt = r.byte()
    if (vmaj, vmin) >= (1, 15):
        compression = {0: "none", 1: "gzip", 2: "lz4", 3: "zstd"}.get(r.byte(), "unknown")
    else:
        level = r.integer(int_size)
        compression = "none" if level == 0 else "gzip"
    for _ in range(7):  # tm_sec, tm_min, tm_hour, tm_mday, tm_mon, tm_year, tm_isdst
        r.integer(int_size)
    dbname = r.string(int_size) if (vmaj, vmin) >= (1, 4) else None
    remote = dumped_by = None
    if (vmaj, vmin) >= (1, 10):
        remote = r.string(int_size)
        dumped_by = r.string(int_size)
    return {"archive_version": f"{vmaj}.{vmin}.{vrev}", "format_code": fmt, "compression": compression, "database": dbname,
            "dumped_from": remote, "dumped_by": dumped_by}


def parse_plain_header(data: bytes) -> dict:
    text = data.decode("utf-8", errors="replace")
    if "PostgreSQL database dump" not in text:
        raise ValueError("not a pg_dump plain-SQL file")
    frm = re.search(r"^-- Dumped from database version\s+(\S+)", text, re.M)
    by = re.search(r"^-- Dumped by pg_dump version\s+(\S+)", text, re.M)
    return {"dumped_from": frm.group(1) if frm else None, "dumped_by": by.group(1) if by else None,
            "has_transaction_timeout_header": bool(re.search(r"^SET transaction_timeout = 0;", text, re.M))}


def major(version: str | None) -> int | None:
    m = re.match(r"(\d+)", version or "")
    return int(m.group(1)) if m else None


def classify(name: str, size: int | None, head: bytes) -> dict:
    row = {"name": name, "size_bytes": size, "format": "unknown"}
    try:
        if head[:5] == MAGIC:
            row.update(format="custom", **parse_custom_header(head))
        else:
            row.update(format="plain", **parse_plain_header(head))
    except (ValueError, EOFError, struct.error) as exc:
        row["note"] = f"unrecognised: {exc}"
        row["restore_hint"] = "Not a recognised pg_dump file: check it by hand before relying on it."
        return row
    by, frm = major(row.get("dumped_by")), major(row.get("dumped_from"))
    if row["format"] == "custom":
        row["restore_hint"] = (
            f"Needs pg_restore {by}+ (an older pg_restore says 'unsupported version')." if by else "pg_dump version not in the header."
        ) + (f" Taken from a PostgreSQL {frm} server; do not restore into an older server." if frm else "")
        if by and frm and by > frm:
            row["restore_hint"] += (f" pg_dump {by} against a {frm} server: a pg_restore {by}+ restoring DIRECTLY into a {frm} server "
                                    "fails on `SET transaction_timeout` unless it goes through the script-stream restore.")
    else:
        row["restore_hint"] = "Plain SQL: restore with psql." + (
            " The header contains `SET transaction_timeout`, which a PostgreSQL 16 or older server rejects until that one line is removed."
            if row.get("has_transaction_timeout_header") else "")
    return row


def from_files(paths: list[str]) -> list[dict]:
    rows = []
    for path in paths:
        with open(path, "rb") as f:
            head = f.read(HEADER_BYTES)
        rows.append(classify(os.path.basename(path), os.path.getsize(path), head))
    return rows


def from_minio(prefix: str, bucket: str | None, limit: int | None) -> list[dict]:
    from minio import Minio  # available in the API image

    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ.get("MINIO_ACCESS_KEY") or os.environ.get("MINIO_ROOT_USER"),
        secret_key=os.environ.get("MINIO_SECRET_KEY") or os.environ.get("MINIO_ROOT_PASSWORD"),
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )
    bucket = bucket or os.environ.get("MINIO_BUCKET", "erpx-storage")
    rows = []
    for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
        if limit and len(rows) >= limit:
            break
        resp = client.get_object(bucket, obj.object_name, offset=0, length=HEADER_BYTES)  # ranged GET: nothing else is downloaded
        try:
            head = resp.read()
        finally:
            resp.close()
            resp.release_conn()
        row = classify(obj.object_name, obj.size, head)
        row["last_modified"] = obj.last_modified.isoformat() if obj.last_modified else None
        rows.append(row)
    return rows


def summarise(rows: list[dict]) -> str:
    out = [f"{'name':58} {'size MB':>8} {'format':7} {'archive':8} {'dumped by':10} {'from server':11}"]
    for r in sorted(rows, key=lambda r: r["name"]):
        out.append(f"{r['name'][-58:]:58} {(r['size_bytes'] or 0) / 1e6:8.1f} {r['format']:7} {r.get('archive_version', '-'):8} "
                   f"{str(r.get('dumped_by') or '-')[:10]:10} {str(r.get('dumped_from') or '-')[:11]:11}")
    groups: dict[tuple, int] = {}
    for r in rows:
        key = (r["format"], r.get("archive_version", "-"), major(r.get("dumped_by")), major(r.get("dumped_from")))
        groups[key] = groups.get(key, 0) + 1
    out.append("")
    out.append("groups (format, archive version, pg_dump major, server major): count")
    for key, n in sorted(groups.items(), key=lambda kv: -kv[1]):
        out.append(f"  {key}: {n}")
    hints = {r["restore_hint"] for r in rows if r.get("restore_hint")}
    out.append("")
    out.append("what that means:")
    out.extend(f"  - {h}" for h in sorted(hints))
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--files", nargs="+")
    src.add_argument("--minio-prefix")
    p.add_argument("--bucket")
    p.add_argument("--limit", type=int, help="inspect at most this many objects")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    rows = from_files(args.files) if args.files else from_minio(args.minio_prefix, args.bucket, args.limit)
    print(json.dumps(rows, indent=1) if args.json else summarise(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
