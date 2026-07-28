import { z } from "zod";

export const categoryFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  slug: z
    .string()
    .min(2, "Slug is required.")
    .regex(/^[a-z0-9-]+$/, "Slug may only contain lowercase letters, numbers, and hyphens."),
  description: z.string().optional().or(z.literal("")),
});
export type CategoryFormValues = z.infer<typeof categoryFormSchema>;
