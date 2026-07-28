import { z } from "zod";

export const gstRateFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  ratePercent: z.string().min(1, "Rate is required."),
  hsnSacCode: z.string().optional().or(z.literal("")),
});
export type GSTRateFormValues = z.infer<typeof gstRateFormSchema>;
