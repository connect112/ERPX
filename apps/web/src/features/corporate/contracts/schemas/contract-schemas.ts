import { z } from "zod";

export const contractTypeValues = ["project", "amc", "retainer", "soc_subscription", "other"] as const;
export type ContractType = (typeof contractTypeValues)[number];

export const contractTypeLabels: Record<ContractType, string> = {
  project: "Project",
  amc: "AMC",
  retainer: "Retainer",
  soc_subscription: "SOC Subscription",
  other: "Other",
};

export const contractStatusValues = ["draft", "active", "expired", "terminated", "renewed"] as const;
export type ContractStatus = (typeof contractStatusValues)[number];

export const contractStatusLabels: Record<ContractStatus, string> = {
  draft: "Draft",
  active: "Active",
  expired: "Expired",
  terminated: "Terminated",
  renewed: "Renewed",
};

export const contractFormSchema = z.object({
  contractNumber: z.string().min(1, "Contract number is required."),
  projectId: z.string().optional().or(z.literal("")),
  quotationId: z.string().optional().or(z.literal("")),
  contractType: z.enum(contractTypeValues),
  startDate: z.string().min(1, "Start date is required."),
  endDate: z.string().optional().or(z.literal("")),
  contractValue: z.coerce.number().min(0, "Must be zero or more."),
  documentUrl: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type ContractFormValues = z.infer<typeof contractFormSchema>;

export const renewContractFormSchema = z.object({
  newEndDate: z.string().min(1, "New end date is required."),
  newContractValue: z.coerce.number().min(0).optional(),
});
export type RenewContractFormValues = z.infer<typeof renewContractFormSchema>;
