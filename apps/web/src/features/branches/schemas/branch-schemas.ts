import { z } from "zod";

export const branchFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  code: z.string().min(1, "Code is required."),
  addressLine1: z.string().optional().or(z.literal("")),
  city: z.string().optional().or(z.literal("")),
  state: z.string().optional().or(z.literal("")),
  country: z.string().optional().or(z.literal("")),
  postalCode: z.string().optional().or(z.literal("")),
  phone: z.string().optional().or(z.literal("")),
  email: z.string().email("Enter a valid email address.").optional().or(z.literal("")),
  isHeadOffice: z.boolean(),
});
export type BranchFormValues = z.infer<typeof branchFormSchema>;
