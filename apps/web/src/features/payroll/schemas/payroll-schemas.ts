import { z } from "zod";

export const salaryComponentTypeValues = ["earning", "deduction"] as const;
export type SalaryComponentType = (typeof salaryComponentTypeValues)[number];

export const salaryComponentTypeLabels: Record<SalaryComponentType, string> = {
  earning: "Earning",
  deduction: "Deduction",
};

export const payrollRunStatusValues = ["draft", "finalized", "paid", "cancelled"] as const;
export type PayrollRunStatus = (typeof payrollRunStatusValues)[number];

export const payrollRunStatusLabels: Record<PayrollRunStatus, string> = {
  draft: "Draft",
  finalized: "Finalized",
  paid: "Paid",
  cancelled: "Cancelled",
};

export const salaryComponentFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  code: z.string().min(1, "Code is required."),
  glAccountId: z.string().min(1, "GL account is required."),
  componentType: z.enum(salaryComponentTypeValues),
  isTaxable: z.boolean(),
});
export type SalaryComponentFormValues = z.infer<typeof salaryComponentFormSchema>;

export const salaryStructureLineFormSchema = z.object({
  salaryComponentId: z.string().min(1, "Component is required."),
  amount: z.coerce.number().min(0, "Amount must be zero or more."),
});

export const salaryStructureFormSchema = z.object({
  effectiveFrom: z.string().min(1, "Effective date is required."),
  notes: z.string().optional().or(z.literal("")),
  lines: z.array(salaryStructureLineFormSchema).min(1, "At least one line is required."),
});
export type SalaryStructureFormValues = z.infer<typeof salaryStructureFormSchema>;

export const generatePayrollRunFormSchema = z.object({
  periodYear: z.coerce.number().min(2000),
  periodMonth: z.coerce.number().min(1).max(12),
  runDate: z.string().min(1, "Run date is required."),
});
export type GeneratePayrollRunFormValues = z.infer<typeof generatePayrollRunFormSchema>;
