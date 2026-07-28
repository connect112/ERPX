import { z } from "zod";

export const tdsSectionFormSchema = z.object({
  sectionCode: z.string().min(2, "Section code is required."),
  description: z.string().min(2, "Description is required."),
  ratePercent: z.string().min(1, "Rate is required."),
  thresholdAmount: z.string().optional().or(z.literal("")),
});
export type TDSSectionFormValues = z.infer<typeof tdsSectionFormSchema>;
