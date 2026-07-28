import { z } from "zod";

export const submissionStatusValues = ["submitted", "graded", "late"] as const;
export type SubmissionStatus = (typeof submissionStatusValues)[number];

export const submissionStatusLabels: Record<SubmissionStatus, string> = {
  submitted: "Submitted",
  graded: "Graded",
  late: "Late",
};

export const assignmentFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  description: z.string().optional().or(z.literal("")),
  dueDate: z.string().optional().or(z.literal("")),
  maxScore: z.string().min(1, "Max score is required."),
});
export type AssignmentFormValues = z.infer<typeof assignmentFormSchema>;

export const submissionFormSchema = z.object({
  studentId: z.string().min(1, "Select a student."),
  contentUrl: z.string().optional().or(z.literal("")),
  contentText: z.string().optional().or(z.literal("")),
});
export type SubmissionFormValues = z.infer<typeof submissionFormSchema>;

export const gradeFormSchema = z.object({
  score: z.string().min(1, "Score is required."),
  feedback: z.string().optional().or(z.literal("")),
});
export type GradeFormValues = z.infer<typeof gradeFormSchema>;
