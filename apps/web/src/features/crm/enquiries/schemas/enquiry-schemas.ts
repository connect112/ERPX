import { z } from "zod";

export const enquiryStatusValues = ["open", "in_progress", "closed"] as const;
export type EnquiryStatus = (typeof enquiryStatusValues)[number];

export const enquiryStatusLabels: Record<EnquiryStatus, string> = {
  open: "Open",
  in_progress: "In Progress",
  closed: "Closed",
};

export const enquiryFormSchema = z.object({
  courseInterest: z.string().min(2, "Course interest is required."),
  budget: z.string().optional().or(z.literal("")),
  preferredBatchTiming: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type EnquiryFormValues = z.infer<typeof enquiryFormSchema>;
