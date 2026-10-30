"""Stream every MinIO object except the in-app database dumps (backups/) as a tar.gz to stdout.

Runs inside the erpx_api container (`docker exec -i erpx_api python -`), so the MinIO credentials never leave
the container. Nothing is written to disk and nothing is modified or deleted in MinIO: it only lists and reads.
A trailing manifest.json records key, size, etag and content type for each object so a restore can re-upload
them with the right metadata. Exit code is non-zero if any object could not be read.
"""

import io
import json
import sys
import tarfile

from minio import Minio

from app.core.config import settings

EXCLUDED_PREFIXES = ("backups/",)  # the in-app SQL dumps: huge, and replaced by the compressed S3 dumps

client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)
bucket = settings.MINIO_BUCKET

manifest = []
errors = 0
out = sys.stdout.buffer
with tarfile.open(fileobj=out, mode="w|gz") as tar:
    for obj in client.list_objects(bucket, recursive=True):
        key = obj.object_name
        if obj.is_dir or key.startswith(EXCLUDED_PREFIXES):
            continue
        resp = None
        try:
            stat = client.stat_object(bucket, key)
            info = tarfile.TarInfo(name="objects/" + key)
            info.size = stat.size
            if stat.last_modified:
                info.mtime = int(stat.last_modified.timestamp())
            resp = client.get_object(bucket, key)
            tar.addfile(info, resp)
            manifest.append(
                {"key": key, "size": stat.size, "etag": stat.etag, "content_type": stat.content_type}
            )
        except Exception as exc:  # noqa: BLE001 - report every failure, keep going, fail at the end
            errors += 1
            print(f"minio_export: failed on {key}: {exc}", file=sys.stderr)
            break  # a half-written tar member cannot be skipped safely
        finally:
            if resp is not None:
                resp.close()
                resp.release_conn()
    body = json.dumps({"bucket": bucket, "count": len(manifest), "objects": manifest}, indent=1).encode()
    meta = tarfile.TarInfo(name="manifest.json")
    meta.size = len(body)
    tar.addfile(meta, io.BytesIO(body))

print(f"minio_export: {len(manifest)} objects, {sum(m['size'] for m in manifest)} bytes", file=sys.stderr)
sys.exit(1 if errors else 0)
