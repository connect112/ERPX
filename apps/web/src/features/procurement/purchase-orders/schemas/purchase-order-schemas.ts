import { z } from "zod";

export const purchaseOrderStatusValues = [
  "draft",
  "sent",
  "partially_received",
  "received",
  "cancelled",
] as const;
export type PurchaseOrderStatus = (typeof purchaseOrderStatusValues)[number];

export const purchaseOrderStatusLabels: Record<PurchaseOrderStatus, string> = {
  draft: "Draft",
  sent: "Sent",
  partially_received: "Partially Received",
  received: "Received",
  cancelled: "Cancelled",
};

export const purchaseOrderLineFormSchema = z.object({
  itemId: z.string().min(1, "Item is required."),
  description: z.string().min(1, "Description is required."),
  quantityOrdered: z.coerce.number().gt(0, "Quantity must be greater than zero."),
  unitPrice: z.coerce.number().min(0, "Unit price must be zero or more."),
  gstRateId: z.string().optional().or(z.literal("")),
});

export const purchaseOrderFormSchema = z.object({
  vendorId: z.string().min(1, "Vendor is required."),
  poNumber: z.string().min(1, "PO number is required."),
  orderDate: z.string().min(1, "Order date is required."),
  expectedDeliveryDate: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
  lines: z.array(purchaseOrderLineFormSchema).min(1, "At least one line is required."),
});
export type PurchaseOrderFormValues = z.infer<typeof purchaseOrderFormSchema>;
