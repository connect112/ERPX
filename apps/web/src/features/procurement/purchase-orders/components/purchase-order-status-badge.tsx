import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type PurchaseOrderStatus,
  purchaseOrderStatusLabels,
} from "@/features/procurement/purchase-orders/schemas/purchase-order-schemas";

const statusVariants: Record<PurchaseOrderStatus, BadgeProps["variant"]> = {
  draft: "secondary",
  sent: "info",
  partially_received: "warning",
  received: "success",
  cancelled: "destructive",
};

export function PurchaseOrderStatusBadge({ status }: { status: PurchaseOrderStatus }) {
  return <Badge variant={statusVariants[status]}>{purchaseOrderStatusLabels[status]}</Badge>;
}
