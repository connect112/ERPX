import { z } from "zod";

export const apPaymentModeValues = ["cash", "bank_transfer", "cheque", "upi", "online"] as const;
export type ApPaymentMode = (typeof apPaymentModeValues)[number];

export const apPaymentModeLabels: Record<ApPaymentMode, string> = {
  cash: "Cash",
  bank_transfer: "Bank Transfer",
  cheque: "Cheque",
  upi: "UPI",
  online: "Online",
};

export const paymentStatusValues = ["cleared", "voided"] as const;
export type PaymentStatus = (typeof paymentStatusValues)[number];

export const paymentStatusLabels: Record<PaymentStatus, string> = {
  cleared: "Cleared",
  voided: "Voided",
};

export const paymentFormSchema = z
  .object({
    vendorId: z.string().min(1, "Select a vendor."),
    expenseId: z.string().min(1, "Select an expense."),
    paymentNumber: z.string().min(1, "Payment number is required."),
    paymentDate: z.string().min(1, "Date is required."),
    grossAmount: z.string().min(1, "Amount is required."),
    paymentMode: z.enum(apPaymentModeValues),
    bankAccountId: z.string().optional().or(z.literal("")),
    paymentAccountId: z.string().optional().or(z.literal("")),
    tdsSectionId: z.string().optional().or(z.literal("")),
    tdsPayableAccountId: z.string().optional().or(z.literal("")),
    referenceNumber: z.string().optional().or(z.literal("")),
    notes: z.string().optional().or(z.literal("")),
  })
  .refine((data) => !!data.bankAccountId || !!data.paymentAccountId, {
    message: "Select a bank account or a payment account.",
    path: ["paymentAccountId"],
  })
  .refine((data) => !data.tdsSectionId || !!data.tdsPayableAccountId, {
    message: "Required when a TDS section is selected.",
    path: ["tdsPayableAccountId"],
  });
export type PaymentFormValues = z.infer<typeof paymentFormSchema>;
