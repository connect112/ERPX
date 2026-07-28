import { z } from "zod";

export const followUpTypeValues = ["call", "email", "meeting", "whatsapp", "sms", "other"] as const;
export type FollowUpType = (typeof followUpTypeValues)[number];

export const followUpTypeLabels: Record<FollowUpType, string> = {
  call: "Call",
  email: "Email",
  meeting: "Meeting",
  whatsapp: "WhatsApp",
  sms: "SMS",
  other: "Other",
};

export const followUpStatusValues = ["scheduled", "completed", "cancelled", "missed"] as const;
export type FollowUpStatus = (typeof followUpStatusValues)[number];

export const followUpStatusLabels: Record<FollowUpStatus, string> = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
  missed: "Missed",
};

export const followUpFormSchema = z.object({
  followUpType: z.enum(followUpTypeValues),
  scheduledAt: z.string().min(1, "Scheduled date/time is required."),
  notes: z.string().optional().or(z.literal("")),
});
export type FollowUpFormValues = z.infer<typeof followUpFormSchema>;

export const followUpCompleteSchema = z.object({
  outcome: z.string().min(1, "Outcome is required."),
  notes: z.string().optional().or(z.literal("")),
});
export type FollowUpCompleteValues = z.infer<typeof followUpCompleteSchema>;
