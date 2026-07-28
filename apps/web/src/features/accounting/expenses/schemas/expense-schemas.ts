import { z } from "zod";

export const expenseStatusValues = [
  "draft",
  "approved",
  "partially_paid",
  "paid",
  "rejected",
  "cancelled",
] as const;
export type ExpenseStatus = (typeof expenseStatusValues)[number];

export const expenseStatusLabels: Record<ExpenseStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  partially_paid: "Partially Paid",
  paid: "Paid",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

export const expenseFormSchema = z
  .object({
    vendorId: z.string().min(1, "Select a vendor."),
    expenseAccountId: z.string().min(1, "Select an expense account."),
    payableAccountId: z.string().min(1, "Select a payable account."),
    expenseNumber: z.string().min(1, "Expense number is required."),
    expenseDate: z.string().min(1, "Date is required."),
    category: z.string().min(2, "Category is required."),
    description: z.string().min(2, "Description is required."),
    subtotalAmount: z.string().min(1, "Amount is required."),
    gstRateId: z.string().optional().or(z.literal("")),
    inputTaxCreditAccountId: z.string().optional().or(z.literal("")),
    isInterstate: z.boolean(),
    attachmentUrl: z.string().optional().or(z.literal("")),
    notes: z.string().optional().or(z.literal("")),
  })
  .refine((data) => !data.gstRateId || !!data.inputTaxCreditAccountId, {
    message: "Required when a GST rate is selected.",
    path: ["inputTaxCreditAccountId"],
  });
export type ExpenseFormValues = z.infer<typeof expenseFormSchema>;
