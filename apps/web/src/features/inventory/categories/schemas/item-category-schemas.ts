import { z } from "zod";

export const itemCategoryFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  code: z.string().min(1, "Code is required."),
  description: z.string().optional().or(z.literal("")),
});
export type ItemCategoryFormValues = z.infer<typeof itemCategoryFormSchema>;
