import { z } from "zod";

export const goodsReceiptLineFormSchema = z.object({
  purchaseOrderLineId: z.string().min(1),
  description: z.string(),
  quantityReceived: z.coerce.number().min(0, "Must be zero or more."),
  unitCost: z.coerce.number().min(0, "Must be zero or more."),
});

export const goodsReceiptFormSchema = z.object({
  warehouseId: z.string().min(1, "Warehouse is required."),
  receiptNumber: z.string().min(1, "Receipt number is required."),
  receiptDate: z.string().min(1, "Receipt date is required."),
  notes: z.string().optional().or(z.literal("")),
  lines: z.array(goodsReceiptLineFormSchema).min(1, "At least one line is required."),
});
export type GoodsReceiptFormValues = z.infer<typeof goodsReceiptFormSchema>;
