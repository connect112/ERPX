import { z } from "zod";

export const examStatusValues = ["draft", "scheduled", "completed", "cancelled"] as const;
export type ExamStatus = (typeof examStatusValues)[number];

export const examStatusLabels: Record<ExamStatus, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const examFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  examDate: z.string().min(1, "Exam date is required."),
  durationMinutes: z.string().min(1, "Duration is required."),
  passingMarks: z.string().min(1, "Passing marks is required."),
});
export type ExamFormValues = z.infer<typeof examFormSchema>;
