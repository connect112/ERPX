import { z } from "zod";

export const depreciationMethodValues = ["straight_line", "declining_balance"] as const;
export type DepreciationMethod = (typeof depreciationMethodValues)[number];

export const depreciationMethodLabels: Record<DepreciationMethod, string> = {
  straight_line: "Straight Line",
  declining_balance: "Declining Balance",
};

export const assetCategoryFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  code: z.string().min(1, "Code is required."),
  defaultUsefulLifeYears: z.coerce.number().min(1, "Must be at least 1 year."),
  defaultDepreciationMethod: z.enum(depreciationMethodValues),
});
export type AssetCategoryFormValues = z.infer<typeof assetCategoryFormSchema>;
