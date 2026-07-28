import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type StudentStatus, studentStatusLabels } from "@/features/students/schemas/student-schemas";

const statusVariants: Record<StudentStatus, BadgeProps["variant"]> = {
  active: "success",
  on_hold: "warning",
  completed: "info",
  dropped: "destructive",
  transferred: "secondary",
};

export function StudentStatusBadge({ status }: { status: StudentStatus }) {
  return <Badge variant={statusVariants[status]}>{studentStatusLabels[status]}</Badge>;
}
