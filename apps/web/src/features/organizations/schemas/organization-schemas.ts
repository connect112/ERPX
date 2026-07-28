import { z } from "zod";

export const subscriptionPlanValues = ["trial", "basic", "professional", "enterprise"] as const;
export type SubscriptionPlan = (typeof subscriptionPlanValues)[number];

export const subscriptionPlanLabels: Record<SubscriptionPlan, string> = {
  trial: "Trial",
  basic: "Basic",
  professional: "Professional",
  enterprise: "Enterprise",
};

export const organizationFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  slug: z
    .string()
    .min(2, "Slug is required.")
    .regex(/^[a-z0-9-]+$/, "Use lowercase letters, numbers, and hyphens only."),
  legalName: z.string().optional().or(z.literal("")),
  industry: z.string().optional().or(z.literal("")),
  email: z.string().email("Enter a valid email address.").optional().or(z.literal("")),
  phone: z.string().optional().or(z.literal("")),
  website: z.string().optional().or(z.literal("")),
  addressLine1: z.string().optional().or(z.literal("")),
  city: z.string().optional().or(z.literal("")),
  state: z.string().optional().or(z.literal("")),
  country: z.string().optional().or(z.literal("")),
  postalCode: z.string().optional().or(z.literal("")),
  subscriptionPlan: z.enum(subscriptionPlanValues),
});
export type OrganizationFormValues = z.infer<typeof organizationFormSchema>;
