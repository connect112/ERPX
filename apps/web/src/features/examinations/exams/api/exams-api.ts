import { apiClient } from "@/api/client";
import type { ExamStatus } from "@/features/examinations/exams/schemas/exam-schemas";

export interface ExamPublic {
  id: string;
  course_id: string;
  title: string;
  exam_date: string;
  duration_minutes: number;
  passing_marks: number;
  status: ExamStatus;
  created_at: string;
}

export interface ExamWithTotalMarks extends ExamPublic {
  total_marks: number;
}

export interface ExamQuestionPublic {
  id: string;
  exam_id: string;
  question_id: string;
  marks_allocated: number;
  order_index: number;
}

export interface ExamCreatePayload {
  title: string;
  exam_date: string;
  duration_minutes?: number;
  passing_marks?: number;
}

export interface ExamUpdatePayload {
  title?: string;
  exam_date?: string;
  duration_minutes?: number;
  passing_marks?: number;
  status?: ExamStatus;
}

const base = (courseId: string) => `/examinations/courses/${courseId}/exams`;

export const examsApi = {
  list: (courseId: string) => apiClient.get<ExamPublic[]>(base(courseId)).then((r) => r.data),

  get: (courseId: string, examId: string) =>
    apiClient.get<ExamWithTotalMarks>(`${base(courseId)}/${examId}`).then((r) => r.data),

  create: (courseId: string, payload: ExamCreatePayload) =>
    apiClient.post<ExamPublic>(base(courseId), payload).then((r) => r.data),

  update: (courseId: string, examId: string, payload: ExamUpdatePayload) =>
    apiClient.patch<ExamPublic>(`${base(courseId)}/${examId}`, payload).then((r) => r.data),

  remove: (courseId: string, examId: string) =>
    apiClient.delete(`${base(courseId)}/${examId}`).then((r) => r.data),

  listQuestions: (courseId: string, examId: string) =>
    apiClient
      .get<ExamQuestionPublic[]>(`${base(courseId)}/${examId}/questions`)
      .then((r) => r.data),

  addQuestion: (
    courseId: string,
    examId: string,
    payload: { question_id: string; marks_allocated: number; order_index: number }
  ) =>
    apiClient
      .post<ExamQuestionPublic>(`${base(courseId)}/${examId}/questions`, payload)
      .then((r) => r.data),

  removeQuestion: (courseId: string, examId: string, questionId: string) =>
    apiClient
      .delete(`${base(courseId)}/${examId}/questions/${questionId}`)
      .then((r) => r.data),
};
