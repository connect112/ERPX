import { Badge, type BadgeProps } from "@/components/ui/badge";
import { type AMCStatus, amcStatusLabels } from "@/features/corporate/amc/schemas/amc-schemas";

const statusVariants: Record<AMCStatus, BadgeProps["variant"]> = {
  active: "success",
  expired: "destructive",
  renewed: "info",
  cancelled: "secondary",
};

export function AMCStatusBadge({ status }: { status: AMCStatus }) {
  return <Badge variant={statusVariants[status]}>{amcStatusLabels[status]}</Badge>;
}
