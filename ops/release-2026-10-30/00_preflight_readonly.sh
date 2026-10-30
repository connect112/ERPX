#!/bin/bash
# STEP 0: READ-ONLY preflight for the Stage 4 + 5 release. It prints facts and changes nothing:
# no git fetch or checkout, no file written, no container touched. Run it once, before any merge.
# Paste into Systems Manager > Run Command > AWS-RunShellScript, target i-0054474b85332980a only.
export LC_ALL=C
COMPOSE="docker compose -f docker-compose.prod.yml"

echo "== 1. time and disk"; date -u; df -h / | tail -1

echo; echo "== 2. source checkout /opt/erpx (is it a clean git checkout the deploy can fast-forward?)"
cd /opt/erpx || { echo "NO /opt/erpx"; exit 1; }
git rev-parse --is-inside-work-tree 2>&1
echo "branch: $(git branch --show-current 2>&1)  HEAD: $(git rev-parse HEAD 2>&1)"
git log -1 --format='last commit: %h %cd %s' --date=iso 2>&1 | cut -c1-160
git remote -v 2>&1 | sed -E 's#//[^@/]*@#//***@#' | head -2
echo "-- tracked changes (must be empty):"; git status --porcelain --untracked-files=no | head -10
echo "-- untracked (informational):"; git status --porcelain | grep '^??' | head -10
echo "-- is HEAD an ancestor of origin/master as last fetched?"; git merge-base --is-ancestor HEAD origin/master 2>&1 && echo yes || echo "no or unknown"

echo; echo "== 3. containers and the images they run (rollback targets)"
$COMPOSE ps --format 'table {{.Name}}\t{{.Status}}' 2>&1 | head -20
for c in erpx_api erpx_celery_worker erpx_celery_beat erpx_web; do
  docker inspect -f '{{.Name}} image={{.Config.Image}} id={{.Image}} created={{.Created}}' "$c" 2>&1
done
echo "-- compose image names:"; $COMPOSE config --images 2>&1 | head -10

echo; echo "== 4. database and effective backup settings (read only)"
docker exec erpx_api alembic current 2>&1 | tail -1
docker exec erpx_api printenv 2>/dev/null | grep -E '^(BACKUP_|RUN_MIGRATIONS|STORAGE_)' | sort
grep -E '^(BACKUP_[A-Z_]*)=' /opt/erpx/.env 2>/dev/null || echo "(no BACKUP_ lines in /opt/erpx/.env: defaults apply)"
echo "-- the newest in-app backup records (these must be untouched by the release):"
docker exec shared_postgres psql -U postgres -d erpx -tA -F ' | ' -c "select left(id::text,8), status, coalesce(storage_key,'(cleared)'), size_bytes, to_char(completed_at,'YYYY-MM-DD HH24:MI') from backup_jobs order by started_at desc limit 8" 2>&1

echo; echo "== 5. off-server backup install on the host (what a release would replace)"
D=/opt/backups/offsite
ls -la $D 2>&1 | head -30
echo "-- sha256 of the live files:"; (cd $D 2>/dev/null && sha256sum *.sh *.py *.sql aws_config 2>/dev/null)
echo "-- last_status.json:"; cat $D/last_status.json 2>&1 | head -c 600; echo
echo "-- timers:"; systemctl list-timers --all 2>/dev/null | grep -E 'offsite|NEXT' | cut -c1-170
for u in offsite-backup.service offsite-backup.timer; do echo "-- /etc/systemd/system/$u:"; cat /etc/systemd/system/$u 2>&1; done
echo "-- live offsite_backup.sh (to diff against the release copy):"; cat $D/offsite_backup.sh 2>&1

echo; echo "== 6. S3 side as the instance sees it (list only)"
aws s3 ls s3://pentrix-erpx-backups-373384939117/daily/ 2>&1 | tail -4

echo; echo "== done (nothing was changed)"
