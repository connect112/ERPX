import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type LeadStatus, leadStatusLabels } from "@/features/crm/leads/schemas/lead-schemas";

const statusVariants: Record<LeadStatus, BadgeProps["variant"]> = {
  new: "info",
  contacted: "secondary",
  qualified: "warning",
  converted: "success",
  lost: "destructive",
};

export function LeadStatusBadge({ status }: { status: LeadStatus }) {
  return <Badge variant={statusVariants[status]}>{leadStatusLabels[status]}</Badge>;
}
