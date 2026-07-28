import { apiClient } from "@/api/client";

export type AttemptStatus = "in_progress" | "submitted" | "evaluated";

export interface ExamAttemptPublic {
  id: string;
  exam_id: string;
  student_id: string;
  started_at: string;
  submitted_at: string | null;
  total_score: number | null;
  status: AttemptStatus;
}

export interface ExamAnswerPublic {
  id: string;
  attempt_id: string;
  question_id: string;
  answer_text: string | null;
  marks_awarded: number | null;
  evaluated_by_user_id: string | null;
}

export const evaluationApi = {
  startAttempt: (examId: string, studentId: string) =>
    apiClient
      .post<ExamAttemptPublic>(`/examinations/exams/${examId}/attempts`, { student_id: studentId })
      .then((r) => r.data),

  submitAnswer: (attemptId: string, questionId: string, answerText?: string) =>
    apiClient
      .post<ExamAnswerPublic>(`/examinations/attempts/${attemptId}/answers`, {
        question_id: questionId,
        answer_text: answerText,
      })
      .then((r) => r.data),

  submitAttempt: (attemptId: string) =>
    apiClient
      .post<ExamAttemptPublic>(`/examinations/attempts/${attemptId}/submit`)
      .then((r) => r.data),

  listAnswers: (attemptId: string) =>
    apiClient
      .get<ExamAnswerPublic[]>(`/examinations/attempts/${attemptId}/answers`)
      .then((r) => r.data),

  gradeAnswer: (answerId: string, marksAwarded: number) =>
    apiClient
      .post<ExamAnswerPublic>(`/examinations/answers/${answerId}/grade`, { marks_awarded: marksAwarded })
      .then((r) => r.data),

  finalizeEvaluation: (attemptId: string) =>
    apiClient
      .post<ExamAttemptPublic>(`/examinations/attempts/${attemptId}/finalize`)
      .then((r) => r.data),
};
