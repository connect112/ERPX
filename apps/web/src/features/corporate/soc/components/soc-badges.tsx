import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type IncidentSeverity,
  type IncidentStatus,
  type SOCServiceStatus,
  incidentSeverityLabels,
  incidentStatusLabels,
  socServiceStatusLabels,
} from "@/features/corporate/soc/schemas/soc-schemas";

const serviceStatusVariants: Record<SOCServiceStatus, BadgeProps["variant"]> = {
  active: "success",
  suspended: "warning",
  terminated: "destructive",
};

export function SOCServiceStatusBadge({ status }: { status: SOCServiceStatus }) {
  return <Badge variant={serviceStatusVariants[status]}>{socServiceStatusLabels[status]}</Badge>;
}

const incidentSeverityVariants: Record<IncidentSeverity, BadgeProps["variant"]> = {
  critical: "destructive",
  high: "warning",
  medium: "info",
  low: "secondary",
};

export function IncidentSeverityBadge({ severity }: { severity: IncidentSeverity }) {
  return <Badge variant={incidentSeverityVariants[severity]}>{incidentSeverityLabels[severity]}</Badge>;
}

const incidentStatusVariants: Record<IncidentStatus, BadgeProps["variant"]> = {
  open: "destructive",
  investigating: "warning",
  contained: "info",
  resolved: "success",
  closed: "secondary",
};

export function IncidentStatusBadge({ status }: { status: IncidentStatus }) {
  return <Badge variant={incidentStatusVariants[status]}>{incidentStatusLabels[status]}</Badge>;
}
