import { z } from "zod";

export const questionTypeValues = ["mcq", "true_false", "short_answer", "essay", "coding"] as const;
export type QuestionType = (typeof questionTypeValues)[number];

export const questionTypeLabels: Record<QuestionType, string> = {
  mcq: "Multiple Choice",
  true_false: "True / False",
  short_answer: "Short Answer",
  essay: "Essay",
  coding: "Coding",
};

export const autoGradableTypes: QuestionType[] = ["mcq", "true_false", "short_answer"];
export const optionsBasedTypes: QuestionType[] = ["mcq", "true_false"];

export const difficultyValues = ["easy", "medium", "hard"] as const;
export type Difficulty = (typeof difficultyValues)[number];

export const difficultyLabels: Record<Difficulty, string> = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
};

export const questionFormSchema = z.object({
  courseId: z.string().optional().or(z.literal("")),
  questionText: z.string().min(2, "Question text is required."),
  questionType: z.enum(questionTypeValues),
  options: z.string().optional().or(z.literal("")),
  correctAnswer: z.string().optional().or(z.literal("")),
  defaultMarks: z.string().min(1, "Marks is required."),
  difficulty: z.enum(difficultyValues),
});
export type QuestionFormValues = z.infer<typeof questionFormSchema>;
