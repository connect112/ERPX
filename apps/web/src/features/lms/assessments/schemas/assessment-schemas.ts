import { z } from "zod";

export const assessmentTypeValues = ["quiz", "mock_test", "coding_test"] as const;
export type AssessmentType = (typeof assessmentTypeValues)[number];

export const assessmentTypeLabels: Record<AssessmentType, string> = {
  quiz: "Quiz",
  mock_test: "Mock Test",
  coding_test: "Coding Test",
};

export const attemptStatusValues = ["in_progress", "submitted", "evaluated"] as const;
export type AttemptStatus = (typeof attemptStatusValues)[number];

export const attemptStatusLabels: Record<AttemptStatus, string> = {
  in_progress: "In Progress",
  submitted: "Submitted",
  evaluated: "Evaluated",
};

export const assessmentFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  assessmentType: z.enum(assessmentTypeValues),
  totalMarks: z.string().min(1, "Total marks is required."),
  passingMarks: z.string().min(1, "Passing marks is required."),
  durationMinutes: z.string().optional().or(z.literal("")),
});
export type AssessmentFormValues = z.infer<typeof assessmentFormSchema>;
