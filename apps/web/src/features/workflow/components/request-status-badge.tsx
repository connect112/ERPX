import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type ApprovalRequestStatus,
  approvalRequestStatusLabels,
} from "@/features/workflow/schemas/workflow-schemas";

const statusVariants: Record<ApprovalRequestStatus, BadgeProps["variant"]> = {
  pending: "warning",
  approved: "success",
  rejected: "destructive",
  cancelled: "secondary",
};

export function RequestStatusBadge({ status }: { status: ApprovalRequestStatus }) {
  return <Badge variant={statusVariants[status]}>{approvalRequestStatusLabels[status]}</Badge>;
}
