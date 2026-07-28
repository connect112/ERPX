import { Database, Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useBackupDownloadUrl, useBackupsList, useTriggerBackup } from "@/features/backups/api/backups-hooks";
import { BackupStatusBadge } from "@/features/backups/components/backup-status-badge";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function BackupsPage() {
  const { data, isLoading, isError } = useBackupsList({ limit: 50 });
  const triggerBackup = useTriggerBackup();
  const downloadUrl = useBackupDownloadUrl();

  const handleDownload = (id: string) => {
    downloadUrl.mutate(id, {
      onSuccess: (url) => {
        const link = document.createElement("a");
        link.href = url;
        link.click();
      },
    });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Database Backups</h1>
          <p className="mt-1 text-muted-foreground">
            Trigger and download full pg_dump snapshots of the database. Administrator-only.
          </p>
        </div>
        <Button onClick={() => triggerBackup.mutate()} disabled={triggerBackup.isPending}>
          <Database className="h-4 w-4" />
          {triggerBackup.isPending ? "Starting..." : "Trigger Backup"}
        </Button>
      </div>

      {triggerBackup.isError && (
        <p className="text-sm text-destructive">
          {(triggerBackup.error as { response?: { data?: { error?: { message?: string } } } })?.response
            ?.data?.error?.message ?? "Could not trigger a backup."}
        </p>
      )}

      <Card>
        <CardContent className="space-y-4 p-6">
          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load backup history. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No backups yet. Trigger one to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Started</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="text-muted-foreground">
                      {new Date(job.started_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{formatBytes(job.size_bytes)}</TableCell>
                    <TableCell>
                      <BackupStatusBadge status={job.status} />
                      {job.status === "failed" && job.error_message && (
                        <p className="mt-1 max-w-xs truncate text-xs text-destructive" title={job.error_message}>
                          {job.error_message}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {job.status === "completed" && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDownload(job.id)}
                          aria-label="Download backup"
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
