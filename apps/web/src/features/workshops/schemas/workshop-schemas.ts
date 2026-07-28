import { z } from "zod";

export const workshopModeValues = ["physical", "virtual"] as const;
export type WorkshopMode = (typeof workshopModeValues)[number];

export const workshopModeLabels: Record<WorkshopMode, string> = {
  physical: "Physical",
  virtual: "Virtual",
};

export const workshopStatusValues = ["draft", "published", "ongoing", "completed", "cancelled"] as const;
export type WorkshopStatus = (typeof workshopStatusValues)[number];

export const workshopStatusLabels: Record<WorkshopStatus, string> = {
  draft: "Draft",
  published: "Published",
  ongoing: "Ongoing",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const workshopFormSchema = z.object({
  code: z.string().min(1, "Code is required."),
  title: z.string().min(2, "Title is required."),
  description: z.string().optional().or(z.literal("")),
  mode: z.enum(workshopModeValues),
  venue: z.string().optional().or(z.literal("")),
  meetingLink: z.string().optional().or(z.literal("")),
  workshopDate: z.string().min(1, "Date is required."),
  startTime: z.string().min(1, "Start time is required."),
  endTime: z.string().min(1, "End time is required."),
  capacity: z.preprocess(
    (val) => (val === "" || val === undefined ? undefined : val),
    z.coerce.number().int().min(1).optional()
  ),
  fee: z.preprocess(
    (val) => (val === "" || val === undefined ? undefined : val),
    z.coerce.number().min(0).optional()
  ),
});
export type WorkshopFormValues = z.infer<typeof workshopFormSchema>;

export const registrationFormSchema = z.object({
  contactName: z.string().min(2, "Name is required."),
  contactEmail: z.string().email("Enter a valid email.").optional().or(z.literal("")),
  contactPhone: z.string().optional().or(z.literal("")),
});
export type RegistrationFormValues = z.infer<typeof registrationFormSchema>;
