"""
List, and only on request remove, in-app backups older than the newest N.

    python -m scripts.prune_backups --keep 7                 # dry run: lists what would go, changes nothing
    python -m scripts.prune_backups --keep 7 --execute       # asks you to type the number of files, then removes them

Never scheduled. Removes only the stored file and clears the job's storage_key (the job row, its checksum and size stay
as history); it never touches the newest N, failed jobs, or anything outside the `backups/` prefix.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db_context
from modules.backups.models import BackupJob
from modules.backups.retention import select_backups_to_prune
from packages.storage.client import get_storage_client


def describe(job: BackupJob) -> str:
    size = f"{(job.size_bytes or 0) / 1024**2:,.0f} MB"
    return f"{job.started_at:%Y-%m-%d %H:%M} UTC  {size:>10}  {job.id}  {job.storage_key}"


async def run(keep: int, execute: bool, reader=input) -> int:
    async with get_db_context() as db:
        jobs = list((await db.execute(select(BackupJob))).scalars().all())
        candidates = select_backups_to_prune(jobs, keep)
        total_mb = sum((j.size_bytes or 0) for j in candidates) / 1024**2
        print(f"Keeping the newest {keep} stored backups. {len(candidates)} older ({total_mb:,.0f} MB) would be removed:")
        for job in candidates:
            print("  " + describe(job))
        if not candidates:
            return 0
        if not execute:
            print("Dry run: nothing was changed. Re-run with --execute to remove them.")
            return 0
        if reader(f"Type {len(candidates)} to confirm removing these {len(candidates)} files: ").strip() != str(len(candidates)):
            print("Aborted: nothing was changed.")
            return 1
        storage = get_storage_client()
        for job in candidates:
            if not job.storage_key.startswith("backups/"):
                print(f"  skipped (outside backups/): {job.storage_key}")
                continue
            await storage.delete_object(job.storage_key)
            job.error_message = f"File removed by retention; it was {job.storage_key}"
            job.storage_key = None
            await db.commit()  # record each removal at once, so a later failure cannot hide one that happened
            print("  removed " + str(job.id))
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prune_backups", description=__doc__.splitlines()[1] if __doc__ else "")
    parser.add_argument("--keep", type=int, default=settings.BACKUP_RETENTION_KEEP_LAST, help="Newest backups to keep.")
    parser.add_argument("--execute", action="store_true", help="Actually remove files (otherwise a dry run).")
    args = parser.parse_args(argv)
    if args.keep <= 0:
        print("Nothing to do: --keep (or BACKUP_RETENTION_KEEP_LAST) must be at least 1.", file=sys.stderr)
        return 1
    return asyncio.run(run(args.keep, args.execute))


if __name__ == "__main__":
    sys.exit(main())
