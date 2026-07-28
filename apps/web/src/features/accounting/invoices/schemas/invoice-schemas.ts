import { z } from "zod";

export const invoiceStatusValues = [
  "draft",
  "sent",
  "partially_paid",
  "paid",
  "overdue",
  "cancelled",
] as const;
export type InvoiceStatus = (typeof invoiceStatusValues)[number];

export const invoiceStatusLabels: Record<InvoiceStatus, string> = {
  draft: "Draft",
  sent: "Sent",
  partially_paid: "Partially Paid",
  paid: "Paid",
  overdue: "Overdue",
  cancelled: "Cancelled",
};

const invoiceLineSchema = z.object({
  revenueAccountId: z.string().min(1, "Select a revenue account."),
  description: z.string().min(1, "Description is required."),
  quantity: z.string().min(1, "Quantity is required."),
  unitPrice: z.string().min(1, "Unit price is required."),
  gstRateId: z.string().optional().or(z.literal("")),
});

export const invoiceFormSchema = z.object({
  customerId: z.string().min(1, "Select a customer."),
  invoiceNumber: z.string().min(1, "Invoice number is required."),
  invoiceDate: z.string().min(1, "Invoice date is required."),
  dueDate: z.string().min(1, "Due date is required."),
  receivableAccountId: z.string().min(1, "Select the receivable account."),
  taxPayableAccountId: z.string().optional().or(z.literal("")),
  discountAccountId: z.string().optional().or(z.literal("")),
  isInterstate: z.boolean(),
  discountAmount: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
  lines: z.array(invoiceLineSchema).min(1, "At least one line is required."),
});
export type InvoiceFormValues = z.infer<typeof invoiceFormSchema>;
export type InvoiceLineFormValues = z.infer<typeof invoiceLineSchema>;
