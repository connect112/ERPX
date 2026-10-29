#!/usr/bin/env bash
# Prove that an off-server backup can actually be restored. Read-only for production: it downloads a backup,
# restores it into a throwaway PostgreSQL container, and compares the result with the backup's manifest.
#
#   AWS_PROFILE=<read-only profile> ./restore_verify.sh [YYYY-MM-DD]
#
# Run it on a machine with docker, the AWS CLI and python3 (a laptop or a spare runner), NOT on the production host:
# a restore needs about the size of the dump again in disk and several hundred MB of memory, which the host lacks.
# The downloaded files hold real personal data; they live in a temp directory that is removed on exit.
# Exit 0 only if every check passes.
set -euo pipefail

BUCKET=${BUCKET:-pentrix-erpx-backups-373384939117}
PG_IMAGE=${PG_IMAGE:-postgres:16-alpine}      # must be the same major version as production (16)
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$(mktemp -d)
NAME=restore_verify_$$
fail=0

cleanup() { docker rm -f "$NAME" > /dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT

if [ -n "${1:-}" ]; then
  DAY=$1
else   # newest daily folder that finished (has SHA256SUMS)
  DAY=""
  for d in $(aws s3 ls "s3://$BUCKET/daily/" | awk '/PRE/{print $2}' | tr -d '/' | sort -r); do
    if aws s3api head-object --bucket "$BUCKET" --key "daily/$d/SHA256SUMS" > /dev/null 2>&1; then DAY=$d; break; fi
  done
  [ -n "$DAY" ] || { echo "no complete backup found"; exit 1; }
fi
echo "verifying backup daily/$DAY"
aws s3 cp "s3://$BUCKET/daily/$DAY/" "$WORK/" --recursive --only-show-errors

echo "1. checksums"
while read -r sum file size; do
  got=$(sha256sum "$WORK/$file" | cut -d' ' -f1)
  [ "$got" = "$sum" ] && echo "   ok   $file ($size bytes)" || { echo "   FAIL $file"; fail=1; }
done < "$WORK/SHA256SUMS"
[ "$fail" = 0 ] || { echo "RESTORE VERIFY FAILED: checksum mismatch"; exit 2; }

echo "2. restore into a throwaway $PG_IMAGE (no ports published)"
docker run -d --name "$NAME" -e POSTGRES_PASSWORD=restore-verify-only -v "$WORK:/b:ro" "$PG_IMAGE" > /dev/null
for _ in $(seq 1 30); do docker exec "$NAME" pg_isready -U postgres > /dev/null 2>&1 && break; sleep 2; done
for DB in erpx pentrix; do
  docker exec "$NAME" createdb -U postgres "${DB}_restored"
  docker exec "$NAME" pg_restore -U postgres -d "${DB}_restored" --no-owner --no-privileges --exit-on-error "/b/$DB.dump"
  echo "   restored $DB"
done

echo "3. migration version and row counts against the manifest"
for DB in erpx pentrix; do
  docker exec -i "$NAME" psql -U postgres -d "${DB}_restored" -tA < "$HERE/counts.sql" > "$WORK/restored-$DB.txt"
  python3 "$HERE/verify_restore.py" "$WORK/manifest.json" "$DB" "$WORK/restored-$DB.txt" || fail=1
done

echo "4. MinIO uploads archive"
python3 "$HERE/verify_minio_tar.py" "$WORK/minio-uploads.tar.gz" || fail=1

if [ "$fail" = 0 ]; then echo "RESTORE VERIFY OK ($DAY)"; else echo "RESTORE VERIFY FAILED ($DAY)"; exit 3; fi
