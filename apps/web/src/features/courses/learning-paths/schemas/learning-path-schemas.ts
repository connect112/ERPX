import { z } from "zod";

export const learningPathFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  slug: z
    .string()
    .min(2, "Slug is required.")
    .regex(/^[a-z0-9-]+$/, "Slug may only contain lowercase letters, numbers, and hyphens."),
  description: z.string().optional().or(z.literal("")),
});
export type LearningPathFormValues = z.infer<typeof learningPathFormSchema>;
