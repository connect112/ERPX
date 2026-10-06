import type { QuestionInput } from "@/features/workshop-exams/api/workshop-exams-api";

export const BLANK_QUESTION: QuestionInput = {
  text: "",
  options: ["", ""],
  correct_indices: [],
  allow_multiple: false,
  marks: 1,
};

/** Why this draft can't be saved yet, or null when it's fine. */
export function questionProblem(q: QuestionInput): string | null {
  if (!q.text.trim()) return "Type the question.";
  const options = q.options.map((o) => o.trim());
  if (options.some((o) => !o)) return "Fill in or remove the empty option.";
  if (new Set(options.map((o) => o.toLowerCase())).size !== options.length) return "Two options are the same.";
  if (q.correct_indices.length === 0) return "Tick the correct answer.";
  if (!q.allow_multiple && q.correct_indices.length !== 1) return "Pick just one correct answer.";
  return null;
}
