import { z } from "zod";

export const practicalFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  examDate: z.string().min(1, "Exam date is required."),
  rubric: z.string().optional().or(z.literal("")),
  totalMarks: z.string().min(1, "Total marks is required."),
  passingMarks: z.string().min(1, "Passing marks is required."),
});
export type PracticalFormValues = z.infer<typeof practicalFormSchema>;

export const recordResultFormSchema = z.object({
  studentId: z.string().min(1, "Select a student."),
  score: z.string().min(1, "Score is required."),
  remarks: z.string().optional().or(z.literal("")),
});
export type RecordResultFormValues = z.infer<typeof recordResultFormSchema>;
