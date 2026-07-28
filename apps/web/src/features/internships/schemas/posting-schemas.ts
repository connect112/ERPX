import { z } from "zod";

export const internshipPostingStatusValues = ["draft", "open", "closed"] as const;
export type InternshipPostingStatus = (typeof internshipPostingStatusValues)[number];

export const internshipPostingStatusLabels: Record<InternshipPostingStatus, string> = {
  draft: "Draft",
  open: "Open",
  closed: "Closed",
};

export const internshipApplicationStatusValues = [
  "applied",
  "shortlisted",
  "selected",
  "rejected",
  "withdrawn",
] as const;
export type InternshipApplicationStatus = (typeof internshipApplicationStatusValues)[number];

export const internshipApplicationStatusLabels: Record<InternshipApplicationStatus, string> = {
  applied: "Applied",
  shortlisted: "Shortlisted",
  selected: "Selected",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export const internshipStatusValues = ["ongoing", "completed", "terminated"] as const;
export type InternshipStatus = (typeof internshipStatusValues)[number];

export const internshipStatusLabels: Record<InternshipStatus, string> = {
  ongoing: "Ongoing",
  completed: "Completed",
  terminated: "Terminated",
};

export const postingFormSchema = z.object({
  companyId: z.string().min(1, "Company is required."),
  title: z.string().min(2, "Title is required."),
  description: z.string().optional().or(z.literal("")),
  durationMonths: z.preprocess(
    (val) => (val === "" || val === undefined ? undefined : val),
    z.coerce.number().int().min(1).max(36).optional()
  ),
  stipend: z.preprocess(
    (val) => (val === "" || val === undefined ? undefined : val),
    z.coerce.number().min(0).optional()
  ),
  location: z.string().optional().or(z.literal("")),
  requiredSkills: z.string().optional().or(z.literal("")),
  applicationDeadline: z.string().optional().or(z.literal("")),
});
export type PostingFormValues = z.infer<typeof postingFormSchema>;
