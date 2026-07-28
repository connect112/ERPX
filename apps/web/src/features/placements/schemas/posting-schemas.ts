import { z } from "zod";

export const jobTypeValues = ["full_time", "part_time", "internship", "contract"] as const;
export type JobType = (typeof jobTypeValues)[number];

export const jobTypeLabels: Record<JobType, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  internship: "Internship",
  contract: "Contract",
};

export const postingStatusValues = ["draft", "open", "closed"] as const;
export type PostingStatus = (typeof postingStatusValues)[number];

export const postingStatusLabels: Record<PostingStatus, string> = {
  draft: "Draft",
  open: "Open",
  closed: "Closed",
};

export const applicationStatusValues = [
  "applied",
  "shortlisted",
  "interview_scheduled",
  "offered",
  "rejected",
  "withdrawn",
] as const;
export type ApplicationStatus = (typeof applicationStatusValues)[number];

export const applicationStatusLabels: Record<ApplicationStatus, string> = {
  applied: "Applied",
  shortlisted: "Shortlisted",
  interview_scheduled: "Interview Scheduled",
  offered: "Offered",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export const postingFormSchema = z.object({
  companyId: z.string().min(1, "Company is required."),
  title: z.string().min(2, "Title is required."),
  description: z.string().optional().or(z.literal("")),
  jobType: z.enum(jobTypeValues),
  location: z.string().optional().or(z.literal("")),
  salaryMin: z.preprocess(
    (val) => (val === "" || val === undefined ? undefined : val),
    z.coerce.number().min(0).optional()
  ),
  salaryMax: z.preprocess(
    (val) => (val === "" || val === undefined ? undefined : val),
    z.coerce.number().min(0).optional()
  ),
  requiredSkills: z.string().optional().or(z.literal("")),
  applicationDeadline: z.string().optional().or(z.literal("")),
});
export type PostingFormValues = z.infer<typeof postingFormSchema>;
