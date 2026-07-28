import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type InternshipPostingStatus,
  internshipPostingStatusLabels,
} from "@/features/internships/schemas/posting-schemas";

const statusVariants: Record<InternshipPostingStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  open: "success",
  closed: "destructive",
};

export function PostingStatusBadge({ status }: { status: InternshipPostingStatus }) {
  return <Badge variant={statusVariants[status]}>{internshipPostingStatusLabels[status]}</Badge>;
}
