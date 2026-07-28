import { z } from "zod";

export const accountTypeValues = ["asset", "liability", "equity", "income", "expense"] as const;
export type AccountType = (typeof accountTypeValues)[number];

export const accountTypeLabels: Record<AccountType, string> = {
  asset: "Asset",
  liability: "Liability",
  equity: "Equity",
  income: "Income",
  expense: "Expense",
};

export const accountFormSchema = z.object({
  code: z.string().min(1, "Code is required."),
  name: z.string().min(2, "Name is required."),
  accountType: z.enum(accountTypeValues),
  accountSubtype: z.string().optional().or(z.literal("")),
  parentAccountId: z.string().optional().or(z.literal("")),
  description: z.string().optional().or(z.literal("")),
  openingBalance: z.string().optional().or(z.literal("")),
});
export type AccountFormValues = z.infer<typeof accountFormSchema>;
