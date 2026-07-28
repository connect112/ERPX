import { apiClient } from "@/api/client";
import type {
  Difficulty,
  QuestionType,
} from "@/features/examinations/question-bank/schemas/question-schemas";

export interface QuestionPublic {
  id: string;
  organization_id: string;
  course_id: string | null;
  question_text: string;
  question_type: QuestionType;
  options: string[] | null;
  correct_answer: string | null;
  default_marks: number;
  difficulty: Difficulty;
  created_at: string;
}

export interface QuestionCreatePayload {
  course_id?: string;
  question_text: string;
  question_type: QuestionType;
  options?: string[];
  correct_answer?: string;
  default_marks?: number;
  difficulty?: Difficulty;
}

export interface QuestionUpdatePayload {
  question_text?: string;
  options?: string[];
  correct_answer?: string;
  default_marks?: number;
  difficulty?: Difficulty;
}

export const questionsApi = {
  list: (courseId?: string) =>
    apiClient
      .get<QuestionPublic[]>("/examinations/question-bank", { params: { course_id: courseId } })
      .then((r) => r.data),

  create: (payload: QuestionCreatePayload) =>
    apiClient.post<QuestionPublic>("/examinations/question-bank", payload).then((r) => r.data),

  update: (id: string, payload: QuestionUpdatePayload) =>
    apiClient
      .patch<QuestionPublic>(`/examinations/question-bank/${id}`, payload)
      .then((r) => r.data),

  remove: (id: string) =>
    apiClient.delete(`/examinations/question-bank/${id}`).then((r) => r.data),
};
