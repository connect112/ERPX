import { z } from "zod";

export const hackathonStatusValues = [
  "draft",
  "registration_open",
  "ongoing",
  "completed",
  "cancelled",
] as const;
export type HackathonStatus = (typeof hackathonStatusValues)[number];

export const hackathonStatusLabels: Record<HackathonStatus, string> = {
  draft: "Draft",
  registration_open: "Registration Open",
  ongoing: "Ongoing",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const hackathonFormSchema = z.object({
  code: z.string().min(1, "Code is required."),
  title: z.string().min(2, "Title is required."),
  theme: z.string().optional().or(z.literal("")),
  description: z.string().optional().or(z.literal("")),
  registrationDeadline: z.string().min(1, "Registration deadline is required."),
  startDate: z.string().min(1, "Start date is required."),
  endDate: z.string().min(1, "End date is required."),
  maxTeamSize: z.preprocess(
    (val) => (val === "" || val === undefined ? undefined : val),
    z.coerce.number().int().min(1).max(20).optional()
  ),
  prizePool: z.preprocess(
    (val) => (val === "" || val === undefined ? undefined : val),
    z.coerce.number().min(0).optional()
  ),
});
export type HackathonFormValues = z.infer<typeof hackathonFormSchema>;
