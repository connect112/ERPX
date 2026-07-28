import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type PayrollRunStatus, payrollRunStatusLabels } from "@/features/payroll/schemas/payroll-schemas";

const statusVariants: Record<PayrollRunStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  finalized: "info",
  paid: "success",
  cancelled: "destructive",
};

export function PayrollRunStatusBadge({ status }: { status: PayrollRunStatus }) {
  return <Badge variant={statusVariants[status]}>{payrollRunStatusLabels[status]}</Badge>;
}
