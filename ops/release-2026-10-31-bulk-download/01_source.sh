#!/bin/bash
# STEP 1 (bulk download release, PR #159): move /opt/erpx to the approved merge commit. No container, backup or host file is touched.
# Paste into Run Command > AWS-RunShellScript on i-0054474b85332980a only, after setting SHA on the next line.
SHA=PASTE_THE_40_CHARACTER_MERGE_COMMIT_HERE
set -euo pipefail

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "SHA is not set to a 40-character commit id; nothing was done"; exit 2; }
cd /opt/erpx
echo "disk:"; df -h / | tail -1
test -z "$(git status --porcelain --untracked-files=no)" || { echo "tracked local changes in /opt/erpx; stopping"; git status --short | head; exit 2; }
echo "alembic now: $(docker exec erpx_api alembic current 2>&1 | tail -1)   (expect 0096 (head))"
test "$(docker exec erpx_api alembic current 2>&1 | tail -1 | cut -c1-4)" = 0096 || { echo "production is not at 0096; stopping"; exit 2; }

echo "== source: $(git rev-parse --short HEAD) -> ${SHA:0:7}"
git fetch origin master
test "$(git cat-file -t "$SHA")" = commit
git merge --ff-only "$SHA"
test "$(git rev-parse HEAD)" = "$SHA"
git log -1 --format='now at %h %s'
test -f apps/api/alembic/versions/0097_bulk_export_jobs.py && echo "migration 0097 present"
echo "== STEP 1 DONE. Nothing is running the new code yet."
