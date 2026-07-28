import { z } from "zod";

export const clientStatusValues = ["prospect", "active", "inactive", "churned"] as const;
export type ClientStatus = (typeof clientStatusValues)[number];

export const clientStatusLabels: Record<ClientStatus, string> = {
  prospect: "Prospect",
  active: "Active",
  inactive: "Inactive",
  churned: "Churned",
};

export const clientFormSchema = z.object({
  clientCode: z.string().min(1, "Code is required."),
  name: z.string().min(2, "Name is required."),
  accountingCustomerId: z.string().optional().or(z.literal("")),
  accountManagerUserId: z.string().optional().or(z.literal("")),
  industry: z.string().optional().or(z.literal("")),
  website: z.string().optional().or(z.literal("")),
  gstin: z.string().optional().or(z.literal("")),
  contactPersonName: z.string().optional().or(z.literal("")),
  contactEmail: z.string().email("Enter a valid email address.").optional().or(z.literal("")),
  contactPhone: z.string().optional().or(z.literal("")),
  addressLine1: z.string().optional().or(z.literal("")),
  city: z.string().optional().or(z.literal("")),
  state: z.string().optional().or(z.literal("")),
  country: z.string().optional().or(z.literal("")),
  postalCode: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type ClientFormValues = z.infer<typeof clientFormSchema>;
