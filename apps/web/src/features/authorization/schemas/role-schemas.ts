import { z } from "zod";

export const roleFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  slug: z
    .string()
    .min(2, "Slug is required.")
    .regex(/^[a-z0-9_]+$/, "Use lowercase letters, numbers, and underscores only."),
  description: z.string().optional().or(z.literal("")),
});
export type RoleFormValues = z.infer<typeof roleFormSchema>;

export const roleUpdateFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  description: z.string().optional().or(z.literal("")),
});
export type RoleUpdateFormValues = z.infer<typeof roleUpdateFormSchema>;
