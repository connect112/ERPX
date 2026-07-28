import { z } from "zod";

export const paymentModeValues = ["cash", "bank_transfer", "cheque", "upi", "card", "online"] as const;
export type PaymentMode = (typeof paymentModeValues)[number];

export const paymentModeLabels: Record<PaymentMode, string> = {
  cash: "Cash",
  bank_transfer: "Bank Transfer",
  cheque: "Cheque",
  upi: "UPI",
  card: "Card",
  online: "Online",
};

export const receiptStatusValues = ["cleared", "voided"] as const;
export type ReceiptStatus = (typeof receiptStatusValues)[number];

export const receiptStatusLabels: Record<ReceiptStatus, string> = {
  cleared: "Cleared",
  voided: "Voided",
};

export const receiptFormSchema = z
  .object({
    customerId: z.string().min(1, "Select a customer."),
    invoiceId: z.string().optional().or(z.literal("")),
    receivableAccountId: z.string().optional().or(z.literal("")),
    receiptNumber: z.string().min(1, "Receipt number is required."),
    receiptDate: z.string().min(1, "Date is required."),
    amount: z.string().min(1, "Amount is required."),
    paymentMode: z.enum(paymentModeValues),
    bankAccountId: z.string().optional().or(z.literal("")),
    depositAccountId: z.string().optional().or(z.literal("")),
    referenceNumber: z.string().optional().or(z.literal("")),
    notes: z.string().optional().or(z.literal("")),
  })
  .refine((data) => !!data.bankAccountId || !!data.depositAccountId, {
    message: "Select a bank account or a deposit account.",
    path: ["depositAccountId"],
  })
  .refine((data) => !!data.invoiceId || !!data.receivableAccountId, {
    message: "Required for an on-account receipt (no invoice selected).",
    path: ["receivableAccountId"],
  });
export type ReceiptFormValues = z.infer<typeof receiptFormSchema>;
