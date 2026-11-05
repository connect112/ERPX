# Backup format inventory (read-only procedure for an authorised operator)

Purpose: find out **which backup formats actually exist** in production and **which PostgreSQL versions made them**, so it is known
what can restore them. Nothing here changes data. It does not prove a backup is restorable (section 5 does, on a different machine).

Who runs it: only an operator the owner has separately authorised for production. An assistant without production access prepares
and reviews; it does not run this.

## Safety properties

- Only `SELECT` statements and **ranged reads of the first 8 KiB** of each backup. No whole backup is downloaded, nothing is written
  to MinIO, S3 or the database, nothing is deleted, no container is restarted.
- `ops/inventory/backup_inventory.py` imports nothing but the standard library (plus the MinIO client that the API image already has).
- Run from a shell on the host through Systems Manager (`AWS-RunShellScript`) or an SSH session, as the owner decides.

## 1. In-app backups: what the database says (read-only SQL)

```bash
docker exec shared_postgres psql -U postgres -d erpx -c "
  select left(id::text,8) as job, status,
         case when storage_key like '%.dump' then 'custom (.dump)' when storage_key like '%.sql' then 'plain (.sql)'
              when storage_key is null then '(pointer cleared)' else 'other' end as format,
         size_bytes, (sha256 is not null) as has_sha256, to_char(completed_at,'YYYY-MM-DD HH24:MI') as completed
  from backup_jobs order by started_at desc limit 40"
```

Look for: how many `.dump` versus `.sql`; any `completed` row without a `sha256`; failed rows and their dates.

## 2. In-app backups: what the files themselves say (header only)

Copy `ops/inventory/backup_inventory.py` to the host from the release checkout (`/opt/erpx/ops/inventory/`), then:

```bash
docker exec -i erpx_api python - --minio-prefix backups/ < /opt/erpx/ops/inventory/backup_inventory.py
```

(`--json` gives machine-readable output; `--limit 10` samples.) The table shows each object's format, archive version, the
`pg_dump` version that made it and the server version it was taken from. The "what that means" lines explain it. The key facts:

| Seen | Meaning |
|---|---|
| `custom`, archive 1.16, pg_dump 17+ from a 16 server | needs a `pg_restore` 17+; a `pg_restore` 16 says `unsupported version (1.16)`; and an **un-fixed** `restore_backup.py` fails on `SET transaction_timeout` |
| `custom`, archive 1.15, pg_dump 16 | restores with `pg_restore` 16 or newer (newer ones need the fixed `restore_backup.py` for a 16 server) |
| `plain` with `SET transaction_timeout` in the header | restore with `psql`, after removing that one header line for a 16 server |
| `unknown` | not a recognised pg_dump file: investigate before relying on it |

## 3. Off-server backups in S3 (header only, with the instance role, which can read but not delete)

```bash
B=pentrix-erpx-backups-373384939117
mkdir -p /tmp/headers && cd /tmp/headers
for d in $(aws s3 ls s3://$B/daily/ | awk '{print $2}' | tr -d / | tail -5); do
  aws s3api get-object --bucket $B --key daily/$d/erpx.dump --range bytes=0-8191 erpx_$d.head >/dev/null
  aws s3api get-object --bucket $B --key daily/$d/pentrix.dump --range bytes=0-8191 pentrix_$d.head >/dev/null
done
python3 /opt/erpx/ops/inventory/backup_inventory.py --files /tmp/headers/*.head
rm -rf /tmp/headers          # the only thing this procedure creates, and it only holds 8 KiB headers
```

These are made by the database container's own `pg_dump` (version 16), so expect `custom`, archive 1.15, `dumped_by 16.x`.
Anything else is a finding. Also confirm each day's folder has `SHA256SUMS` and `manifest.json`.

## 4. Reading the result

For every group in the output, write down: **format, pg_dump version, server version, count, newest date**. Then answer:

1. Which backups exist in a format that only a 17+ client can read?
2. Which tool would restore each, into a PostgreSQL 16 server, **today** (before the restore fix is deployed) and **after** it?
3. Is there at least one recent backup of each kind that has been rehearsed (section 5)?

## 5. Proving restorability (separate step, never on production)

A header cannot show that the rest of the file is intact. On a **non-production** machine, with a copy of one recent backup of each
kind (download it there; do not restore on the production host):

```bash
pg_restore --list backup.dump | head                       # readable by this client?  (custom)
pg_restore --no-owner --no-privileges -f /dev/null backup.dump   # reads the whole archive; exit 0 = not damaged
python -m scripts.restore_backup --backup-file backup.dump --database-url <drill db url> --dry-run   # after the fix is deployed
python -m scripts.restore_backup --backup-file backup.dump --database-url <drill db url>           # restore into an EMPTY drill database
```

Record the client version used, the server version, the result and the time it took. `docs/operations/offsite-backup.md` has the
equivalent rehearsal for the S3 dumps (`restore_verify.sh`).

## 6. What to report back

The group table from sections 2 and 3, the counts from section 1, and the rehearsal result from section 5. Do not paste connection
strings, keys or file contents.
