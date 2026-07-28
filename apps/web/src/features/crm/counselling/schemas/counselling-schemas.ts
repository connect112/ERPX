import { z } from "zod";

export const counsellingModeValues = ["online", "offline", "phone"] as const;
export type CounsellingMode = (typeof counsellingModeValues)[number];

export const counsellingModeLabels: Record<CounsellingMode, string> = {
  online: "Online",
  offline: "Offline",
  phone: "Phone",
};

export const counsellingStatusValues = ["scheduled", "completed", "cancelled", "no_show"] as const;
export type CounsellingStatus = (typeof counsellingStatusValues)[number];

export const counsellingStatusLabels: Record<CounsellingStatus, string> = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
  no_show: "No Show",
};

export const counsellingFormSchema = z.object({
  mode: z.enum(counsellingModeValues),
  scheduledAt: z.string().min(1, "Scheduled date/time is required."),
  notes: z.string().optional().or(z.literal("")),
});
export type CounsellingFormValues = z.infer<typeof counsellingFormSchema>;

export const counsellingCompleteSchema = z.object({
  recommendedCourse: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type CounsellingCompleteValues = z.infer<typeof counsellingCompleteSchema>;
