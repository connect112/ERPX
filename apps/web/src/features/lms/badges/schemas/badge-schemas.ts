import { z } from "zod";

export const badgeFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  description: z.string().optional().or(z.literal("")),
  iconUrl: z.string().optional().or(z.literal("")),
});
export type BadgeFormValues = z.infer<typeof badgeFormSchema>;
