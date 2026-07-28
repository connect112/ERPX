import { z } from "zod";

export const bankAccountTypeValues = ["savings", "current", "cash"] as const;
export type BankAccountType = (typeof bankAccountTypeValues)[number];

export const bankAccountTypeLabels: Record<BankAccountType, string> = {
  savings: "Savings",
  current: "Current",
  cash: "Cash",
};

export const bankTransactionSourceValues = ["manual", "receipt", "payment", "import"] as const;
export type BankTransactionSource = (typeof bankTransactionSourceValues)[number];

export const bankAccountFormSchema = z.object({
  glAccountId: z.string().min(1, "Select a GL account."),
  accountName: z.string().min(2, "Account name is required."),
  accountType: z.enum(bankAccountTypeValues),
  bankName: z.string().optional().or(z.literal("")),
  accountNumber: z.string().optional().or(z.literal("")),
  ifscCode: z.string().optional().or(z.literal("")),
  openingBalance: z.string().optional().or(z.literal("")),
});
export type BankAccountFormValues = z.infer<typeof bankAccountFormSchema>;

export const bankTransactionFormSchema = z.object({
  transactionDate: z.string().min(1, "Date is required."),
  description: z.string().min(2, "Description is required."),
  debitAmount: z.string().optional().or(z.literal("")),
  creditAmount: z.string().optional().or(z.literal("")),
  referenceNumber: z.string().optional().or(z.literal("")),
  contraAccountId: z.string().min(1, "Select the contra account."),
});
export type BankTransactionFormValues = z.infer<typeof bankTransactionFormSchema>;
