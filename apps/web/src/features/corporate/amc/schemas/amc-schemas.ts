import { z } from "zod";

export const billingFrequencyValues = ["monthly", "quarterly", "annually"] as const;
export type BillingFrequency = (typeof billingFrequencyValues)[number];

export const billingFrequencyLabels: Record<BillingFrequency, string> = {
  monthly: "Monthly",
  quarterly: "Quarterly",
  annually: "Annually",
};

export const amcStatusValues = ["active", "expired", "renewed", "cancelled"] as const;
export type AMCStatus = (typeof amcStatusValues)[number];

export const amcStatusLabels: Record<AMCStatus, string> = {
  active: "Active",
  expired: "Expired",
  renewed: "Renewed",
  cancelled: "Cancelled",
};

export const amcVisitStatusValues = ["scheduled", "completed", "cancelled"] as const;
export type AMCVisitStatus = (typeof amcVisitStatusValues)[number];

export const amcVisitStatusLabels: Record<AMCVisitStatus, string> = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const amcContractFormSchema = z.object({
  amcNumber: z.string().min(1, "AMC number is required."),
  coverageDescription: z.string().min(2, "Coverage description is required."),
  startDate: z.string().min(1, "Start date is required."),
  endDate: z.string().min(1, "End date is required."),
  renewalReminderDays: z.coerce.number().min(1).default(30),
  amount: z.coerce.number().min(0, "Must be zero or more."),
  billingFrequency: z.enum(billingFrequencyValues),
});
export type AMCContractFormValues = z.infer<typeof amcContractFormSchema>;

export const amcVisitFormSchema = z.object({
  visitDate: z.string().min(1, "Visit date is required."),
  purpose: z.string().min(2, "Purpose is required."),
  engineerEmployeeId: z.string().optional().or(z.literal("")),
});
export type AMCVisitFormValues = z.infer<typeof amcVisitFormSchema>;
