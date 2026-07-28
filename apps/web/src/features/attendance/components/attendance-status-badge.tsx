import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type AttendanceStatus,
  attendanceStatusLabels,
} from "@/features/attendance/schemas/attendance-schemas";

const statusVariants: Record<AttendanceStatus, BadgeProps["variant"]> = {
  present: "success",
  absent: "destructive",
  half_day: "warning",
  on_leave: "info",
  holiday: "secondary",
  week_off: "outline",
};

export function AttendanceStatusBadge({ status }: { status: AttendanceStatus }) {
  return <Badge variant={statusVariants[status]}>{attendanceStatusLabels[status]}</Badge>;
}
