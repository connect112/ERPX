import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type FindingSeverity,
  type FindingStatus,
  type VAPTEngagementStatus,
  findingSeverityLabels,
  findingStatusLabels,
  vaptEngagementStatusLabels,
} from "@/features/corporate/vapt/schemas/vapt-schemas";

const engagementStatusVariants: Record<VAPTEngagementStatus, BadgeProps["variant"]> = {
  scoping: "secondary",
  in_progress: "info",
  reporting: "warning",
  retest: "warning",
  closed: "success",
};

export function VAPTEngagementStatusBadge({ status }: { status: VAPTEngagementStatus }) {
  return <Badge variant={engagementStatusVariants[status]}>{vaptEngagementStatusLabels[status]}</Badge>;
}

const findingSeverityVariants: Record<FindingSeverity, BadgeProps["variant"]> = {
  critical: "destructive",
  high: "warning",
  medium: "info",
  low: "secondary",
  informational: "outline",
};

export function FindingSeverityBadge({ severity }: { severity: FindingSeverity }) {
  return <Badge variant={findingSeverityVariants[severity]}>{findingSeverityLabels[severity]}</Badge>;
}

const findingStatusVariants: Record<FindingStatus, BadgeProps["variant"]> = {
  open: "destructive",
  retesting: "warning",
  fixed: "success",
  accepted_risk: "secondary",
  false_positive: "outline",
};

export function FindingStatusBadge({ status }: { status: FindingStatus }) {
  return <Badge variant={findingStatusVariants[status]}>{findingStatusLabels[status]}</Badge>;
}
