import { z } from "zod";
import { coerceNumber } from "@/lib/zod-helpers";

export const itemFormSchema = z.object({
  sku: z.string().min(1, "SKU is required."),
  name: z.string().min(2, "Name is required."),
  categoryId: z.string().optional().or(z.literal("")),
  description: z.string().optional().or(z.literal("")),
  unitOfMeasure: z.string().min(1, "Unit of measure is required."),
  reorderLevel: coerceNumber().min(0, "Must be zero or more.").default(0),
  reorderQuantity: coerceNumber().min(0, "Must be zero or more.").default(0),
  standardCost: coerceNumber().min(0, "Must be zero or more.").default(0),
});
export type ItemFormValues = z.infer<typeof itemFormSchema>;
