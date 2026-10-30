"""Build pentrix-op-delete-old-dumps.json, the SSM command document that removes the four approved October 2026 dumps.

Writes a file only. Nothing is registered with AWS and nothing runs: someone with the right to create SSM documents has
to do that, after the owner has read the file. Run: python build_delete_doc.py
"""
import base64
import json
import pathlib

HERE = pathlib.Path(__file__).parent
source = (HERE / "delete_old_dumps.py").read_text(encoding="utf-8").replace("\r\n", "\n")

# load the approved ids from the source of truth, so the document and the code can never disagree
namespace = {}
exec(compile(source.split("class MinioStore")[0], "delete_old_dumps", "exec"), namespace)
ids = ",".join(f"'{a[0]}'" for a in namespace["APPROVED"])
payload = base64.b64encode(source.encode("utf-8")).decode("ascii")

FACTS_SQL = (
    "select json_build_object("
    f"'rows', (select coalesce(json_agg(json_build_object('id', id, 'status', status::text, 'size_bytes', size_bytes, "
    f"'sha256', sha256, 'storage_key', storage_key, 'started_at', started_at)), '[]'::json) from backup_jobs where id::text in ({ids})), "
    "'newest', (select coalesce(json_agg(t), '[]'::json) from (select id, status::text as status, size_bytes, storage_key, "
    "started_at from backup_jobs where status = 'completed' order by started_at desc limit 3) t))"
)
PSQL = "docker exec shared_postgres psql -U postgres -d erpx"

commands = [
    "set -euo pipefail",
    "MODE='{{ Mode }}'",
    "CONFIRM='{{ Confirm }}'",
    'echo "mode: $MODE"',
    'if [ "$MODE" = "delete" ] && [ "$CONFIRM" != "DELETE-4-OLD-DUMPS" ]; then echo "ABORT: the confirmation phrase is missing or wrong. Nothing was changed."; exit 3; fi',
    "echo '== gate 1: the off-server backup is fresh and verified =='",
    'STATUS=$(cat /opt/backups/offsite/last_status.json); echo "$STATUS"',
    'echo "$STATUS" | grep -q \'"ok":true\' || { echo "ABORT: the last off-server backup is not green. Nothing was changed."; exit 4; }',
    'AT=$(echo "$STATUS" | sed -n \'s/.*"at":"\\([^"]*\\)".*/\\1/p\'); AGE=$(( $(date -u +%s) - $(date -u -d "$AT" +%s) )); echo "age of that backup: $AGE seconds"; '
    '[ "$AGE" -lt 100800 ] || { echo "ABORT: the last off-server backup is older than 28 hours. Nothing was changed."; exit 4; }',
    'STAMP=$(echo "$STATUS" | sed -n \'s/.*"stamp":"\\([^"]*\\)".*/\\1/p\')',
    'AWS_CONFIG_FILE=/opt/backups/offsite/aws_config AWS_DEFAULT_REGION=us-east-1 aws s3api head-object --bucket pentrix-erpx-backups-373384939117 '
    '--key "daily/$STAMP/SHA256SUMS" > /dev/null || { echo "ABORT: the S3 backup for $STAMP has no SHA256SUMS. Nothing was changed."; exit 4; }',
    'echo "S3 backup $STAMP is complete (SHA256SUMS present)"',
    "echo '== gate 2: facts from the database (read-only) =='",
    f'facts() {{ {PSQL} -tA -c "{FACTS_SQL}"; }}',
    "FACTS=$(facts)",
    "echo '== gate 3: verify the files, then (delete mode only) remove them =='",
    f"printf '%s' '{payload}' | base64 -d > /tmp/ro_delete.py",
    'OUT=$(mktemp); RC=0',
    'nice -n 19 ionice -c3 docker exec -i -e MODE="$MODE" -e DATA_JSON="$FACTS" erpx_api python - < /tmp/ro_delete.py > "$OUT" 2>&1 || RC=$?',
    'grep -v \'^SQL|\' "$OUT" || true',
    '[ "$RC" = "0" ] || { echo "STOPPED (code $RC). The lines above say exactly what, if anything, was done."; rm -f "$OUT" /tmp/ro_delete.py; exit "$RC"; }',
    'if [ "$MODE" = "delete" ]; then grep \'^SQL|\' "$OUT" | sed \'s/^SQL|//\' > /tmp/ro_update.sql || true; '
    f'if [ -s /tmp/ro_update.sql ]; then echo "== recording the removal (one transaction) =="; (echo "begin;"; cat /tmp/ro_update.sql; echo "commit;") | {PSQL} -v ON_ERROR_STOP=1; fi; '
    'rm -f /tmp/ro_update.sql; fi',
    'rm -f "$OUT"',
    "echo '== post-cleanup checks =='",
    f'{PSQL} -tA -F " | " -c "select started_at::date, id, status, size_bytes, storage_key is null as file_pointer_cleared from backup_jobs where id::text in ({ids}) order by started_at"',
    f'{PSQL} -tA -F " | " -c "select started_at, status, size_bytes, storage_key from backup_jobs order by started_at desc limit 4"',
    'df -h / | tail -1',
    "echo \"containers: $(docker ps | awk 'NR>1' | wc -l) running, $(docker ps | grep -c unhealthy || true) unhealthy\"",
    'docker exec erpx_api curl -fsS http://localhost:8000/api/v1/health; echo',
    'if [ "$MODE" = "delete" ]; then echo "== verify again: the four should read as already removed and the newest three present =="; '
    'FACTS=$(facts); nice -n 19 docker exec -i -e MODE=verify -e DATA_JSON="$FACTS" erpx_api python - < /tmp/ro_delete.py; fi',
    'rm -f /tmp/ro_delete.py',
    "echo DONE",
]

doc = {
    "schemaVersion": "2.2",
    "description": "Removes the four approved in-app database dumps of 8-11 Oct 2026 from MinIO after re-verifying them, and "
                   "clears their records' file pointer. Default Mode=verify changes nothing. Mode=delete needs the confirmation phrase.",
    "parameters": {
        "Mode": {"type": "String", "description": "verify (default) changes nothing; delete removes the four files.",
                 "default": "verify", "allowedValues": ["verify", "delete"]},
        "Confirm": {"type": "String", "description": "For Mode=delete only: type DELETE-4-OLD-DUMPS",
                    "default": "", "allowedPattern": "^[A-Z0-9-]{0,40}$"},
    },
    "mainSteps": [{"action": "aws:runShellScript", "name": "verifyThenDelete",
                   "inputs": {"runCommand": commands, "timeoutSeconds": "3600"}}],
}
out = HERE / "pentrix-op-delete-old-dumps.json"
out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
print("wrote", out.name, len(commands), "commands")
