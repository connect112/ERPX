import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type InternshipStatus,
  internshipStatusLabels,
} from "@/features/internships/schemas/posting-schemas";

const statusVariants: Record<InternshipStatus, BadgeProps["variant"]> = {
  ongoing: "info",
  completed: "success",
  terminated: "destructive",
};

export function InternshipStatusBadge({ status }: { status: InternshipStatus }) {
  return <Badge variant={statusVariants[status]}>{internshipStatusLabels[status]}</Badge>;
}
