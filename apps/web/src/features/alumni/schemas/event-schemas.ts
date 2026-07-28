import { z } from "zod";

export const eventModeValues = ["physical", "virtual"] as const;
export type EventMode = (typeof eventModeValues)[number];

export const eventModeLabels: Record<EventMode, string> = {
  physical: "Physical",
  virtual: "Virtual",
};

export const eventStatusValues = ["draft", "published", "completed", "cancelled"] as const;
export type EventStatus = (typeof eventStatusValues)[number];

export const eventStatusLabels: Record<EventStatus, string> = {
  draft: "Draft",
  published: "Published",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const registrationStatusValues = ["registered", "attended", "cancelled"] as const;
export type RegistrationStatus = (typeof registrationStatusValues)[number];

export const registrationStatusLabels: Record<RegistrationStatus, string> = {
  registered: "Registered",
  attended: "Attended",
  cancelled: "Cancelled",
};

export const referralStatusValues = ["open", "closed"] as const;
export type ReferralStatus = (typeof referralStatusValues)[number];

export const referralStatusLabels: Record<ReferralStatus, string> = {
  open: "Open",
  closed: "Closed",
};

export const eventFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  description: z.string().optional().or(z.literal("")),
  mode: z.enum(eventModeValues),
  venue: z.string().optional().or(z.literal("")),
  meetingLink: z.string().optional().or(z.literal("")),
  eventDate: z.string().min(1, "Event date is required."),
  registrationDeadline: z.string().optional().or(z.literal("")),
});
export type EventFormValues = z.infer<typeof eventFormSchema>;
