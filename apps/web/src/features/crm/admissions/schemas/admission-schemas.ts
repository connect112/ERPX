import { z } from "zod";

export const admissionStatusValues = ["on_hold", "confirmed", "cancelled"] as const;
export type AdmissionStatus = (typeof admissionStatusValues)[number];

export const admissionStatusLabels: Record<AdmissionStatus, string> = {
  on_hold: "On Hold",
  confirmed: "Confirmed",
  cancelled: "Cancelled",
};

export const admissionFormSchema = z.object({
  courseName: z.string().min(2, "Course name is required."),
  batchName: z.string().optional().or(z.literal("")),
  feeAmount: z.string().min(1, "Fee amount is required."),
  discountAmount: z.string().optional().or(z.literal("")),
  admissionDate: z.string().min(1, "Admission date is required."),
});
export type AdmissionFormValues = z.infer<typeof admissionFormSchema>;
