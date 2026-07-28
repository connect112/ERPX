import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { HealthStatus } from "@/features/monitoring/api/monitoring-api";

const statusVariants: Record<HealthStatus, BadgeProps["variant"]> = {
  healthy: "success",
  degraded: "warning",
  unhealthy: "destructive",
};

const statusLabels: Record<HealthStatus, string> = {
  healthy: "Healthy",
  degraded: "Degraded",
  unhealthy: "Unhealthy",
};

export function HealthStatusBadge({ status }: { status: HealthStatus }) {
  return <Badge variant={statusVariants[status]}>{statusLabels[status]}</Badge>;
}
