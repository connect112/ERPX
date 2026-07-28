import { z } from "zod";

export const stockTransactionTypeValues = [
  "purchase_receipt",
  "sale_issue",
  "adjustment_in",
  "adjustment_out",
  "transfer_in",
  "transfer_out",
] as const;
export type StockTransactionType = (typeof stockTransactionTypeValues)[number];

export const stockTransactionTypeLabels: Record<StockTransactionType, string> = {
  purchase_receipt: "Purchase Receipt",
  sale_issue: "Sale Issue",
  adjustment_in: "Adjustment In",
  adjustment_out: "Adjustment Out",
  transfer_in: "Transfer In",
  transfer_out: "Transfer Out",
};

export const receiveStockFormSchema = z.object({
  itemId: z.string().min(1, "Item is required."),
  warehouseId: z.string().min(1, "Warehouse is required."),
  quantity: z.coerce.number().gt(0, "Quantity must be greater than zero."),
  unitCost: z.coerce.number().min(0, "Unit cost must be zero or more."),
  notes: z.string().optional().or(z.literal("")),
});
export type ReceiveStockFormValues = z.infer<typeof receiveStockFormSchema>;

export const issueStockFormSchema = z.object({
  itemId: z.string().min(1, "Item is required."),
  warehouseId: z.string().min(1, "Warehouse is required."),
  quantity: z.coerce.number().gt(0, "Quantity must be greater than zero."),
  notes: z.string().optional().or(z.literal("")),
});
export type IssueStockFormValues = z.infer<typeof issueStockFormSchema>;

export const adjustStockFormSchema = z.object({
  itemId: z.string().min(1, "Item is required."),
  warehouseId: z.string().min(1, "Warehouse is required."),
  quantityChange: z.coerce.number().refine((v) => v !== 0, "Quantity change cannot be zero."),
  unitCost: z.coerce.number().min(0, "Unit cost must be zero or more.").default(0),
  reason: z.string().min(2, "Reason is required."),
});
export type AdjustStockFormValues = z.infer<typeof adjustStockFormSchema>;

export const transferStockFormSchema = z.object({
  itemId: z.string().min(1, "Item is required."),
  fromWarehouseId: z.string().min(1, "Source warehouse is required."),
  toWarehouseId: z.string().min(1, "Destination warehouse is required."),
  quantity: z.coerce.number().gt(0, "Quantity must be greater than zero."),
  notes: z.string().optional().or(z.literal("")),
});
export type TransferStockFormValues = z.infer<typeof transferStockFormSchema>;
