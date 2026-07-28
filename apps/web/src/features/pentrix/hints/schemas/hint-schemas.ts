import { z } from "zod";

export const hintFormSchema = z.object({
  hintText: z.string().min(1, "Hint text is required."),
  pointCost: z.string().min(1, "Point cost is required."),
  orderIndex: z.string().min(1, "Order is required."),
});
export type HintFormValues = z.infer<typeof hintFormSchema>;
