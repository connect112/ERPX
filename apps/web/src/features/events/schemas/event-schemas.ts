import { z } from "zod";

export const eventTypeValues = ["holiday", "meeting", "announcement", "other"] as const;
export type EventType = (typeof eventTypeValues)[number];

export const eventTypeLabels: Record<EventType, string> = {
  holiday: "Holiday",
  meeting: "Meeting",
  announcement: "Announcement",
  other: "Other",
};

export const eventFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  description: z.string().optional().or(z.literal("")),
  eventType: z.enum(eventTypeValues),
  startAt: z.string().min(1, "Start date/time is required."),
  endAt: z.string().optional().or(z.literal("")),
  location: z.string().optional().or(z.literal("")),
  isAllDay: z.boolean(),
});
export type EventFormValues = z.infer<typeof eventFormSchema>;
