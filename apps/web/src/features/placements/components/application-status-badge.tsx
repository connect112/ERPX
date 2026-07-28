import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type ApplicationStatus,
  applicationStatusLabels,
} from "@/features/placements/schemas/posting-schemas";

const statusVariants: Record<ApplicationStatus, BadgeProps["variant"]> = {
  applied: "info",
  shortlisted: "secondary",
  interview_scheduled: "warning",
  offered: "success",
  rejected: "destructive",
  withdrawn: "secondary",
};

export function ApplicationStatusBadge({ status }: { status: ApplicationStatus }) {
  return <Badge variant={statusVariants[status]}>{applicationStatusLabels[status]}</Badge>;
}
