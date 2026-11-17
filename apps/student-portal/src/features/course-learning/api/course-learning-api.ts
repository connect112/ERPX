import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

export interface MyInternshipRef {
  id: string;
  title: string;
  status: string;
  open_assignments: number;
  open_exams: number;
}
export interface MyAssessment {
  id: string;
  title: string;
  assessment_type: string;
  duration_minutes: number | null;
  total_marks: number;
  internship_id: string | null;
  has_questions: boolean;
  state: "not_started" | "in_progress" | "submitted";
  score: number | null;
  result_total: number | null;
  passed: boolean | null;
}
export interface MyEvaluation {
  id: string;
  title: string;
  exam_date: string;
  internship_id: string | null;
  total_marks: number;
  passing_marks: number;
  detail: string | null;
  score: number | null;
  remarks: string | null;
  passed: boolean | null;
}
export interface MyCourseLearning {
  course_id: string;
  course_title: string;
  enrollment_status: string;
  progress: { percent_complete: number; completed_lessons: number; total_lessons: number };
  internships: MyInternshipRef[];
  assessments: MyAssessment[];
  practicals: MyEvaluation[];
  viva: MyEvaluation[];
}
export interface TakeState {
  attempt_id: string;
  status: string;
  remaining_seconds: number | null;
  questions: { id: string; text: string; marks: number; allow_multiple: boolean; options: { index: number; text: string }[] }[];
  saved_answers: Record<string, number[]>;
}
export interface TakeResult {
  attempt_id: string;
  status: string;
  submitted_at: string | null;
  score: number | null;
  total_marks: number | null;
  passed: boolean | null;
}
export interface Thread {
  id: string;
  internship_id: string | null;
  author_name: string | null;
  title: string;
  body: string;
  is_locked: boolean;
  created_at: string;
}
export interface Reply {
  id: string;
  author_name: string | null;
  body: string;
  created_at: string;
}

const a = (courseId: string, id: string) => `/lms/courses/${courseId}/assessments/${id}`;
const d = (courseId: string) => `/lms/courses/${courseId}/discussions`;

export const courseLearningApi = {
  course: (courseId: string) => apiClient.get<MyCourseLearning>(`/my-learning/courses/${courseId}`).then((r) => r.data),
  start: (courseId: string, id: string) => apiClient.post<TakeState>(`${a(courseId, id)}/take/start`).then((r) => r.data),
  save: (courseId: string, id: string, answers: Record<string, number[]>) => apiClient.put(`${a(courseId, id)}/take/answers`, { answers }).then((r) => r.data),
  submit: (courseId: string, id: string, answers: Record<string, number[]>) => apiClient.post<TakeResult>(`${a(courseId, id)}/take/submit`, { answers }).then((r) => r.data),
  result: (courseId: string, id: string) => apiClient.get<TakeResult | null>(`${a(courseId, id)}/take/result`).then((r) => r.data),
  threads: (courseId: string) => apiClient.get<Thread[]>(d(courseId)).then((r) => r.data),
  createThread: (courseId: string, payload: { title: string; body: string; internship_id?: string | null }) => apiClient.post<Thread>(d(courseId), payload).then((r) => r.data),
  replies: (courseId: string, threadId: string) => apiClient.get<Reply[]>(`${d(courseId)}/${threadId}/replies`).then((r) => r.data),
  reply: (courseId: string, threadId: string, body: string) => apiClient.post<Reply>(`${d(courseId)}/${threadId}/replies`, { body }).then((r) => r.data),
};

export const courseLearningKeys = {
  course: (id: string) => ["course-learning", id] as const,
  threads: (id: string) => ["course-learning", id, "threads"] as const,
  replies: (threadId: string) => ["course-learning", "replies", threadId] as const,
};

export function useCourseLearning(courseId: string | undefined) {
  return useQuery({ queryKey: courseLearningKeys.course(courseId ?? ""), queryFn: () => courseLearningApi.course(courseId!), enabled: !!courseId, retry: false });
}
export function useThreads(courseId: string | undefined) {
  return useQuery({ queryKey: courseLearningKeys.threads(courseId ?? ""), queryFn: () => courseLearningApi.threads(courseId!), enabled: !!courseId });
}
export function useReplies(courseId: string, threadId: string, enabled: boolean) {
  return useQuery({ queryKey: courseLearningKeys.replies(threadId), queryFn: () => courseLearningApi.replies(courseId, threadId), enabled });
}
export function useCreateThread(courseId: string) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (p: { title: string; body: string; internship_id?: string | null }) => courseLearningApi.createThread(courseId, p), onSuccess: () => qc.invalidateQueries({ queryKey: courseLearningKeys.threads(courseId) }) });
}
export function useReply(courseId: string, threadId: string) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (body: string) => courseLearningApi.reply(courseId, threadId, body), onSuccess: () => qc.invalidateQueries({ queryKey: courseLearningKeys.replies(threadId) }) });
}
