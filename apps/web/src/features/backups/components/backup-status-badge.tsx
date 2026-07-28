import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { BackupStatus } from "@/features/backups/api/backups-api";

const statusVariants: Record<BackupStatus, BadgeProps["variant"]> = {
  pending: "secondary",
  running: "info",
  completed: "success",
  failed: "destructive",
};

const statusLabels: Record<BackupStatus, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export function BackupStatusBadge({ status }: { status: BackupStatus }) {
  return <Badge variant={statusVariants[status]}>{statusLabels[status]}</Badge>;
}
