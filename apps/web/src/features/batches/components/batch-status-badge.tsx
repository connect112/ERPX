import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { BatchStatus } from "@/features/batches/api/batches-api";

const statusVariants: Record<BatchStatus, BadgeProps["variant"]> = {
  upcoming: "info",
  ongoing: "success",
  completed: "secondary",
  cancelled: "destructive",
};

const statusLabels: Record<BatchStatus, string> = {
  upcoming: "Upcoming",
  ongoing: "Ongoing",
  completed: "Completed",
  cancelled: "Cancelled",
};

export function BatchStatusBadge({ status }: { status: BatchStatus }) {
  return <Badge variant={statusVariants[status]}>{statusLabels[status]}</Badge>;
}
