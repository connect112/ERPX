"""
Backup retention: which finished backups are older than the newest N.

Pure selection logic, no I/O, so it is unit-tested. Nothing here deletes anything and nothing runs it on a schedule:
scripts/prune_backups.py lists the candidates (a dry run) and only removes files when a person passes --execute and
types the confirmation. BACKUP_RETENTION_KEEP_LAST=0 (the default) means keep every backup.
"""

from modules.backups.models import BackupJob, BackupStatus


def select_backups_to_prune(jobs: list[BackupJob], keep_last: int) -> list[BackupJob]:
    """Completed backups that still have a stored file, oldest first, excluding the newest `keep_last`.

    Failed, running or already-pruned jobs are never candidates (they have no file to remove). With keep_last <= 0
    nothing is selected, which is the safe default."""
    if keep_last <= 0:
        return []
    stored = [j for j in jobs if j.status == BackupStatus.COMPLETED and j.storage_key]
    newest_first = sorted(stored, key=lambda j: j.started_at, reverse=True)
    return sorted(newest_first[keep_last:], key=lambda j: j.started_at)
