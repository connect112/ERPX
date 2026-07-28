import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { LiveClassStatus } from "@/features/live-classes/api/live-classes-api";

const statusVariants: Record<LiveClassStatus, BadgeProps["variant"]> = {
  scheduled: "info",
  live: "success",
  completed: "secondary",
  cancelled: "destructive",
};

const statusLabels: Record<LiveClassStatus, string> = {
  scheduled: "Scheduled",
  live: "Live",
  completed: "Completed",
  cancelled: "Cancelled",
};

export function LiveClassStatusBadge({ status }: { status: LiveClassStatus }) {
  return <Badge variant={statusVariants[status]}>{statusLabels[status]}</Badge>;
}
