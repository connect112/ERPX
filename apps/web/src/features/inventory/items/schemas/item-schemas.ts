import { z } from "zod";

export const itemFormSchema = z.object({
  sku: z.string().min(1, "SKU is required."),
  name: z.string().min(2, "Name is required."),
  categoryId: z.string().optional().or(z.literal("")),
  description: z.string().optional().or(z.literal("")),
  unitOfMeasure: z.string().min(1, "Unit of measure is required."),
  reorderLevel: z.coerce.number().min(0, "Must be zero or more.").default(0),
  reorderQuantity: z.coerce.number().min(0, "Must be zero or more.").default(0),
  standardCost: z.coerce.number().min(0, "Must be zero or more.").default(0),
});
export type ItemFormValues = z.infer<typeof itemFormSchema>;
