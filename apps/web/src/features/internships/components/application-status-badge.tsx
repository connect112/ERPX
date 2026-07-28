import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type InternshipApplicationStatus,
  internshipApplicationStatusLabels,
} from "@/features/internships/schemas/posting-schemas";

const statusVariants: Record<InternshipApplicationStatus, BadgeProps["variant"]> = {
  applied: "info",
  shortlisted: "secondary",
  selected: "success",
  rejected: "destructive",
  withdrawn: "secondary",
};

export function ApplicationStatusBadge({ status }: { status: InternshipApplicationStatus }) {
  return <Badge variant={statusVariants[status]}>{internshipApplicationStatusLabels[status]}</Badge>;
}
