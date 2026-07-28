import { z } from "zod";

export const warehouseFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  code: z.string().min(1, "Code is required."),
  addressLine1: z.string().optional().or(z.literal("")),
  city: z.string().optional().or(z.literal("")),
  state: z.string().optional().or(z.literal("")),
  country: z.string().optional().or(z.literal("")),
  postalCode: z.string().optional().or(z.literal("")),
});
export type WarehouseFormValues = z.infer<typeof warehouseFormSchema>;
