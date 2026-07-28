import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  type StockTransactionType,
  stockTransactionTypeLabels,
} from "@/features/inventory/stock/schemas/stock-schemas";

const typeVariants: Record<StockTransactionType, BadgeProps["variant"]> = {
  purchase_receipt: "success",
  sale_issue: "destructive",
  adjustment_in: "info",
  adjustment_out: "warning",
  transfer_in: "info",
  transfer_out: "warning",
};

export function StockTransactionTypeBadge({ type }: { type: StockTransactionType }) {
  return <Badge variant={typeVariants[type]}>{stockTransactionTypeLabels[type]}</Badge>;
}
