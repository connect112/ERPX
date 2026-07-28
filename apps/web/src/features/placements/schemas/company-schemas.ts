import { z } from "zod";

export const companyFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  industry: z.string().optional().or(z.literal("")),
  website: z.string().optional().or(z.literal("")),
  contactPersonName: z.string().optional().or(z.literal("")),
  contactEmail: z.string().email("Enter a valid email.").optional().or(z.literal("")),
  contactPhone: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type CompanyFormValues = z.infer<typeof companyFormSchema>;
