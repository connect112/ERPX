import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type EmploymentStatus,
  employmentStatusLabels,
} from "@/features/employees/schemas/employee-schemas";

const statusVariants: Record<EmploymentStatus, BadgeProps["variant"]> = {
  active: "success",
  on_leave: "info",
  suspended: "warning",
  resigned: "secondary",
  terminated: "destructive",
  retired: "secondary",
};

export function EmployeeStatusBadge({ status }: { status: EmploymentStatus }) {
  return <Badge variant={statusVariants[status]}>{employmentStatusLabels[status]}</Badge>;
}
