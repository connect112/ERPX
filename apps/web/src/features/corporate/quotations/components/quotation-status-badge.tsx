import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type QuotationStatus,
  quotationStatusLabels,
} from "@/features/corporate/quotations/schemas/quotation-schemas";

const statusVariants: Record<QuotationStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  sent: "info",
  accepted: "success",
  rejected: "destructive",
  expired: "warning",
};

export function QuotationStatusBadge({ status }: { status: QuotationStatus }) {
  return <Badge variant={statusVariants[status]}>{quotationStatusLabels[status]}</Badge>;
}
