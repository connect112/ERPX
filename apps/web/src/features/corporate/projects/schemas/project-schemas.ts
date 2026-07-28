import { z } from "zod";

export const projectTypeValues = ["vapt", "soc", "consulting", "training", "other"] as const;
export type ProjectType = (typeof projectTypeValues)[number];

export const projectTypeLabels: Record<ProjectType, string> = {
  vapt: "VAPT",
  soc: "SOC",
  consulting: "Consulting",
  training: "Training",
  other: "Other",
};

export const projectStatusValues = [
  "planned",
  "in_progress",
  "on_hold",
  "completed",
  "cancelled",
] as const;
export type ProjectStatus = (typeof projectStatusValues)[number];

export const projectStatusLabels: Record<ProjectStatus, string> = {
  planned: "Planned",
  in_progress: "In Progress",
  on_hold: "On Hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const projectFormSchema = z.object({
  projectCode: z.string().min(1, "Code is required."),
  name: z.string().min(2, "Name is required."),
  description: z.string().optional().or(z.literal("")),
  projectType: z.enum(projectTypeValues),
  projectManagerEmployeeId: z.string().optional().or(z.literal("")),
  startDate: z.string().min(1, "Start date is required."),
  endDate: z.string().optional().or(z.literal("")),
  budgetAmount: z.coerce.number().min(0).optional(),
  notes: z.string().optional().or(z.literal("")),
});
export type ProjectFormValues = z.infer<typeof projectFormSchema>;
