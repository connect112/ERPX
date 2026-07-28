import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type LeaveApplicationStatus,
  leaveApplicationStatusLabels,
} from "@/features/leave/schemas/leave-schemas";

const statusVariants: Record<LeaveApplicationStatus, BadgeProps["variant"]> = {
  pending: "warning",
  approved: "success",
  rejected: "destructive",
  cancelled: "secondary",
};

export function LeaveStatusBadge({ status }: { status: LeaveApplicationStatus }) {
  return <Badge variant={statusVariants[status]}>{leaveApplicationStatusLabels[status]}</Badge>;
}
