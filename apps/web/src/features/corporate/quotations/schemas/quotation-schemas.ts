import { z } from "zod";

export const quotationStatusValues = ["draft", "sent", "accepted", "rejected", "expired"] as const;
export type QuotationStatus = (typeof quotationStatusValues)[number];

export const quotationStatusLabels: Record<QuotationStatus, string> = {
  draft: "Draft",
  sent: "Sent",
  accepted: "Accepted",
  rejected: "Rejected",
  expired: "Expired",
};

export const quotationLineFormSchema = z.object({
  description: z.string().min(1, "Description is required."),
  quantity: z.coerce.number().gt(0, "Quantity must be greater than zero.").default(1),
  unitPrice: z.coerce.number().min(0, "Unit price must be zero or more."),
  gstRateId: z.string().optional().or(z.literal("")),
});

export const quotationFormSchema = z.object({
  quotationNumber: z.string().min(1, "Quotation number is required."),
  projectId: z.string().optional().or(z.literal("")),
  quotationDate: z.string().min(1, "Quotation date is required."),
  validUntil: z.string().min(1, "Valid-until date is required."),
  notes: z.string().optional().or(z.literal("")),
  lines: z.array(quotationLineFormSchema).min(1, "At least one line is required."),
});
export type QuotationFormValues = z.infer<typeof quotationFormSchema>;
