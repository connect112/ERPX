#!/usr/bin/env bash
# Off-server backup of ERPX + Pentrix to S3. Streams everything: no large local files.
#   erpx.dump, pentrix.dump : pg_dump -Fc (compressed custom format)
#   minio-uploads.tar.gz    : every MinIO object except backups/ (see minio_export.py)
#   SHA256SUMS              : written LAST. A backup folder without it is incomplete and must not be used.
# Layout: daily/YYYY-MM-DD/ always; copied server-side to weekly/ on Sundays and monthly/ on the 1st.
# Retention is enforced by the bucket's lifecycle rules, not by this script (it has no delete rights).
set -euo pipefail

export AWS_DEFAULT_REGION=us-east-1
export AWS_CONFIG_FILE=/opt/backups/offsite/aws_config
BUCKET=pentrix-erpx-backups-373384939117
STAMP=$(date -u +%F)
PREFIX="daily/$STAMP"
STATE=/opt/backups/offsite/last_status.json
WORK=$(mktemp -d /tmp/offsite.XXXXXX)              # only tiny checksum files live here
LOCK=/var/lock/offsite-backup.lock

exec 9>"$LOCK"
flock -n 9 || { echo "another backup is running"; exit 3; }

fail() {
  printf '{"ok":false,"stamp":"%s","at":"%s","error":"%s"}\n' "$STAMP" "$(date -u +%FT%TZ)" "$1" > "$STATE"
  echo "OFFSITE BACKUP FAILED: $1" >&2
}
trap 'rc=$?; rm -rf "$WORK"; [ $rc -ne 0 ] && fail "exit $rc"; exit $rc' EXIT

aws s3api head-bucket --bucket "$BUCKET"

# stdin -> S3 object, recording the sha256 of exactly the bytes sent
upload() {
  local name=$1
  tee >(sha256sum | cut -d' ' -f1 > "$WORK/$name.sha") \
    | aws s3 cp - "s3://$BUCKET/$PREFIX/$name" --expected-size 5000000000 --only-show-errors
  for _ in $(seq 1 60); do [ -s "$WORK/$name.sha" ] && break; sleep 1; done
  [ -s "$WORK/$name.sha" ]
}

for DB in erpx pentrix; do
  echo "dumping $DB"
  nice -n 19 docker exec shared_postgres pg_dump -U postgres -d "$DB" -Fc -Z 6 | upload "$DB.dump"
done

echo "exporting MinIO uploads"
nice -n 19 docker exec -i erpx_api python - < /opt/backups/offsite/minio_export.py | upload minio-uploads.tar.gz

echo "recording manifest (migration version and table row counts)"
for DB in erpx pentrix; do
  docker exec -i shared_postgres psql -U postgres -d "$DB" -tA < /opt/backups/offsite/counts.sql > "$WORK/counts-$DB.txt"
done
python3 /opt/backups/offsite/make_manifest.py "$STAMP" "erpx=$WORK/counts-erpx.txt" "pentrix=$WORK/counts-pentrix.txt" \
  | upload manifest.json

echo "verifying by reading back from S3"
: > "$WORK/SHA256SUMS"
for f in erpx.dump pentrix.dump minio-uploads.tar.gz manifest.json; do
  back=$(aws s3 cp "s3://$BUCKET/$PREFIX/$f" - --only-show-errors | sha256sum | cut -d' ' -f1)
  want=$(cat "$WORK/$f.sha")
  [ "$back" = "$want" ] || { echo "CHECKSUM MISMATCH on $f"; exit 2; }
  size=$(aws s3api head-object --bucket "$BUCKET" --key "$PREFIX/$f" --query ContentLength --output text)
  [ "$size" -gt 1000 ] || { echo "$f is suspiciously small ($size bytes)"; exit 2; }
  echo "$want  $f  $size" >> "$WORK/SHA256SUMS"
done
for DB in erpx pentrix; do      # the dump's table of contents must be readable
  # pg_restore stops after the TOC; drain the rest so aws does not see a broken pipe
  aws s3 cp "s3://$BUCKET/$PREFIX/$DB.dump" - --only-show-errors \
    | { rc=0; docker exec -i shared_postgres pg_restore --list > /dev/null || rc=$?; cat > /dev/null; exit $rc; }
done
aws s3 cp "$WORK/SHA256SUMS" "s3://$BUCKET/$PREFIX/SHA256SUMS" --only-show-errors

if [ "$(date -u +%u)" = "7" ]; then
  aws s3 cp "s3://$BUCKET/$PREFIX/" "s3://$BUCKET/weekly/$STAMP/" --recursive --only-show-errors
fi
if [ "$(date -u +%d)" = "01" ]; then
  aws s3 cp "s3://$BUCKET/$PREFIX/" "s3://$BUCKET/monthly/$STAMP/" --recursive --only-show-errors
fi

total=$(awk '{s+=$3} END{print s}' "$WORK/SHA256SUMS")
printf '{"ok":true,"stamp":"%s","at":"%s","bytes":%s}\n' "$STAMP" "$(date -u +%FT%TZ)" "$total" > "$STATE"
cat "$WORK/SHA256SUMS"
echo "OFFSITE BACKUP OK $STAMP"
