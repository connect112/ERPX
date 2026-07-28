import { z } from "zod";

export const depreciationRunStatusValues = ["draft", "posted", "cancelled"] as const;
export type DepreciationRunStatus = (typeof depreciationRunStatusValues)[number];

export const depreciationRunStatusLabels: Record<DepreciationRunStatus, string> = {
  draft: "Draft",
  posted: "Posted",
  cancelled: "Cancelled",
};

export const generateDepreciationRunFormSchema = z.object({
  periodYear: z.coerce.number().min(2000),
  periodMonth: z.coerce.number().min(1).max(12),
  runDate: z.string().min(1, "Run date is required."),
});
export type GenerateDepreciationRunFormValues = z.infer<typeof generateDepreciationRunFormSchema>;
