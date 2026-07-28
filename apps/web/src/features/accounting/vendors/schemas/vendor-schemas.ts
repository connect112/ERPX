import { z } from "zod";

export const vendorFormSchema = z.object({
  vendorCode: z.string().min(1, "Code is required."),
  name: z.string().min(2, "Name is required."),
  email: z.string().email("Enter a valid email address.").optional().or(z.literal("")),
  phone: z.string().optional().or(z.literal("")),
  gstin: z.string().optional().or(z.literal("")),
  panNumber: z.string().optional().or(z.literal("")),
  addressLine1: z.string().optional().or(z.literal("")),
  addressLine2: z.string().optional().or(z.literal("")),
  city: z.string().optional().or(z.literal("")),
  state: z.string().optional().or(z.literal("")),
  country: z.string().optional().or(z.literal("")),
  postalCode: z.string().optional().or(z.literal("")),
  bankAccountNumber: z.string().optional().or(z.literal("")),
  bankIfscCode: z.string().optional().or(z.literal("")),
  bankName: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type VendorFormValues = z.infer<typeof vendorFormSchema>;
