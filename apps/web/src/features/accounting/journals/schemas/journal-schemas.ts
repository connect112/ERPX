import { z } from "zod";

export const journalEntryStatusValues = ["draft", "posted", "reversed"] as const;
export type JournalEntryStatus = (typeof journalEntryStatusValues)[number];

export const journalEntryStatusLabels: Record<JournalEntryStatus, string> = {
  draft: "Draft",
  posted: "Posted",
  reversed: "Reversed",
};

export const journalSourceModuleValues = [
  "manual",
  "invoices",
  "receipts",
  "expenses",
  "payments",
  "bank",
  "payroll",
  "assets",
] as const;
export type JournalSourceModule = (typeof journalSourceModuleValues)[number];

export const journalSourceModuleLabels: Record<JournalSourceModule, string> = {
  manual: "Manual",
  invoices: "Invoices",
  receipts: "Receipts",
  expenses: "Expenses",
  payments: "Payments",
  bank: "Bank",
  payroll: "Payroll",
  assets: "Assets",
};

const journalLineSchema = z.object({
  accountId: z.string().min(1, "Select an account."),
  description: z.string().optional().or(z.literal("")),
  debit: z.string().optional().or(z.literal("")),
  credit: z.string().optional().or(z.literal("")),
});

export const journalEntryFormSchema = z.object({
  entryDate: z.string().min(1, "Entry date is required."),
  memo: z.string().optional().or(z.literal("")),
  lines: z.array(journalLineSchema).min(2, "At least two lines are required."),
});
export type JournalEntryFormValues = z.infer<typeof journalEntryFormSchema>;
export type JournalLineFormValues = z.infer<typeof journalLineSchema>;
