import { z } from "zod";

export const eventTypeValues = ["holiday", "meeting", "announcement", "other"] as const;
export type EventType = (typeof eventTypeValues)[number];

export const eventTypeLabels: Record<EventType, string> = {
  holiday: "Holiday",
  meeting: "Meeting",
  announcement: "Announcement",
  other: "Other",
};

// Every field is mandatory: the organizer must supply full event details.
export const eventFormSchema = z
  .object({
    title: z.string().trim().min(2, "Title is required."),
    description: z.string().trim().min(1, "Description is required."),
    eventType: z.enum(eventTypeValues, {
      errorMap: () => ({ message: "Type is required." }),
    }),
    startAt: z.string().min(1, "Start date/time is required."),
    endAt: z.string().min(1, "End date/time is required."),
    location: z.string().trim().min(1, "Location is required."),
    isAllDay: z.boolean(),
  })
  .superRefine((values, ctx) => {
    // End must be strictly after start (both are required above).
    if (values.startAt && values.endAt && new Date(values.endAt) <= new Date(values.startAt)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["endAt"],
        message: "End must be after the start.",
      });
    }
  });
export type EventFormValues = z.infer<typeof eventFormSchema>;
