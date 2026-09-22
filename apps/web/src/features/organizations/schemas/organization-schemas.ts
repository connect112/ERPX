import { z } from "zod";

export const subscriptionPlanValues = ["trial", "basic", "professional", "enterprise"] as const;
export type SubscriptionPlan = (typeof subscriptionPlanValues)[number];

export const subscriptionPlanLabels: Record<SubscriptionPlan, string> = {
  trial: "Trial",
  basic: "Basic",
  professional: "Professional",
  enterprise: "Enterprise",
};

const sharedFields = {
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
};

// Editing an existing organization never touches its admin account —
// only creation does (see organization-form-dialog.tsx), which always
// provisions the org's first Administrator and emails them a
// set-password link, so there's no separate "now add an admin" step
// afterward. Both branches below infer the exact same TS type (adminFullName/
// adminEmail are always plain `string`, never optional) so the dialog's
// single useForm<OrganizationFormValues> can swap resolvers by mode
// without a type mismatch — only the runtime validation strictness
// differs.
export function organizationFormSchema(mode: "create" | "edit") {
  return z.object({
    ...sharedFields,
    adminFullName: mode === "create" ? z.string().min(2, "Admin name is required.") : z.string(),
    adminEmail: mode === "create" ? z.string().email("Enter a valid email address.") : z.string(),
  });
}
export type OrganizationFormValues = z.infer<ReturnType<typeof organizationFormSchema>>;
