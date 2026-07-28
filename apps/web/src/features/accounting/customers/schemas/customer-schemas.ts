import { z } from "zod";

export const customerTypeValues = ["individual", "student", "corporate"] as const;
export type CustomerType = (typeof customerTypeValues)[number];

export const customerTypeLabels: Record<CustomerType, string> = {
  individual: "Individual",
  student: "Student",
  corporate: "Corporate",
};

export const customerFormSchema = z.object({
  customerCode: z.string().min(1, "Code is required."),
  name: z.string().min(2, "Name is required."),
  customerType: z.enum(customerTypeValues),
  email: z.string().email("Enter a valid email address.").optional().or(z.literal("")),
  phone: z.string().optional().or(z.literal("")),
  gstin: z.string().optional().or(z.literal("")),
  billingAddressLine1: z.string().optional().or(z.literal("")),
  billingAddressLine2: z.string().optional().or(z.literal("")),
  city: z.string().optional().or(z.literal("")),
  state: z.string().optional().or(z.literal("")),
  country: z.string().optional().or(z.literal("")),
  postalCode: z.string().optional().or(z.literal("")),
  creditLimit: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type CustomerFormValues = z.infer<typeof customerFormSchema>;
