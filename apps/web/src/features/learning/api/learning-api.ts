import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

/** One shared client for the Learning workspace: the same calls serve the internship page and the course page. */

export interface TabDef {
  key: string;
  label: string;
}
export interface InternshipRef {
  id: string;
  title: string;
  status: string;
  can_view: boolean;
  can_manage: boolean;
  can_delete: boolean;
}
export interface LearningContext {
  tabs: TabDef[];
  course: { id: string; title: string; course_type: string; is_published: boolean } | null;
  internships: InternshipRef[];
  needs_selector: boolean;
  course_caps: Record<string, boolean>;
}
export interface EnrollmentRow {
  selection_id: string;
  student_id: string;
  lms_student_id: string | null;
  name: string;
  email: string;
  stage_label: string;
  lms_status: "not_granted" | "granted" | "revoked";
  lms_granted_at: string | null;
  has_account: boolean;
  enrollment_id: string | null;
  enrollment_status: string | null;
  enrolled_on: string | null;
  provenance: "internship" | "independent" | null;
  grant_blockers: string[];
  progress_percent: number | null;
  completed_lessons: number | null;
  total_lessons: number | null;
}
export interface EnrollmentsView {
  internship_id: string;
  course_id: string | null;
  rows: EnrollmentRow[];
  independent: { enrollment_id: string; student_id: string; name: string; status: string; enrolled_on: string }[] | null;
}
export type ResultKind = "exam" | "assignment" | "assessment" | "project" | "practical" | "viva";
export interface ResultRow {
  kind: ResultKind;
  scope: "internship" | "course";
  activity_id: string;
  activity_title: string;
  internship_id: string | null;
  student_key: string;
  lms_student_id: string | null;
  student_name: string;
  student_email: string | null;
  access_status: "granted" | "revoked" | null;
  state: string;
  completed: boolean;
  score: number | null;
  total_marks: number | null;
  percent: number | null;
  passed: boolean | null;
  at: string | null;
}
export interface ResultsView {
  internship_id: string | null;
  course_id: string | null;
  rows: ResultRow[];
  included: ResultKind[];
}
export interface ResultsFilter {
  kind?: string;
  status?: string;
  q?: string;
  student?: string;
  activity_id?: string;
}

export const learningKeys = {
  all: ["learning"] as const,
  context: (scope: { courseId?: string; internshipId?: string }) => ["learning", "context", scope.courseId ?? "", scope.internshipId ?? ""] as const,
  enrollments: (internshipId: string) => ["learning", "enrollments", internshipId] as const,
  results: (scope: { courseId?: string; internshipId?: string }, f: ResultsFilter) => ["learning", "results", scope.courseId ?? "", scope.internshipId ?? "", f] as const,
};

export const learningApi = {
  context: (scope: { courseId?: string; internshipId?: string }) =>
    apiClient.get<LearningContext>("/learning/context", { params: scope.internshipId ? { internship_id: scope.internshipId } : { course_id: scope.courseId } }).then((r) => r.data),
  enrollments: (internshipId: string) => apiClient.get<EnrollmentsView>("/learning/enrollments", { params: { internship_id: internshipId } }).then((r) => r.data),
  results: (scope: { courseId?: string; internshipId?: string }, f: ResultsFilter) =>
    apiClient
      .get<ResultsView>("/learning/results", { params: { ...(scope.internshipId ? { internship_id: scope.internshipId } : { course_id: scope.courseId }), ...f } })
      .then((r) => r.data),
};

export function useLearningContext(scope: { courseId?: string; internshipId?: string }) {
  return useQuery({ queryKey: learningKeys.context(scope), queryFn: () => learningApi.context(scope), enabled: !!(scope.courseId || scope.internshipId) });
}
export function useLearningEnrollments(internshipId: string | undefined) {
  return useQuery({ queryKey: learningKeys.enrollments(internshipId ?? ""), queryFn: () => learningApi.enrollments(internshipId!), enabled: !!internshipId });
}
export function useLearningResults(scope: { courseId?: string; internshipId?: string }, filter: ResultsFilter) {
  return useQuery({ queryKey: learningKeys.results(scope, filter), queryFn: () => learningApi.results(scope, filter), enabled: !!(scope.courseId || scope.internshipId) });
}

// ------------------------------------------------------------------ assessments (quizzes, mock tests, coding tests)

export interface Assessment {
  id: string;
  course_id: string;
  internship_id: string | null;
  title: string;
  assessment_type: "quiz" | "mock_test" | "coding_test";
  total_marks: number;
  passing_marks: number;
  duration_minutes: number | null;
  is_published: boolean;
  show_result: boolean;
}
export interface AssessmentPayload {
  title: string;
  assessment_type: Assessment["assessment_type"];
  total_marks: number;
  passing_marks: number;
  duration_minutes?: number | null;
  internship_id?: string | null;
  show_result?: boolean;
}
export interface Question {
  id: string;
  assessment_id: string;
  text: string;
  options: string[];
  correct_indices: number[];
  allow_multiple: boolean;
  marks: number;
  order_index: number;
}
export interface QuestionPayload {
  text: string;
  options: string[];
  correct_indices: number[];
  allow_multiple: boolean;
  marks: number;
}
export interface Attempt {
  id: string;
  assessment_id: string;
  student_id: string;
  student_name: string | null;
  started_at: string;
  submitted_at: string | null;
  score: number | null;
  total_marks: number | null;
  status: string;
  access_status: string | null;
}

const assessments = (courseId: string) => `/lms/courses/${courseId}/assessments`;
export const assessmentsApi = {
  list: (courseId: string, internshipId?: string | null) =>
    apiClient.get<Assessment[]>(assessments(courseId), { params: internshipId ? { internship_id: internshipId, include_course: true } : {} }).then((r) => r.data),
  create: (courseId: string, payload: AssessmentPayload) => apiClient.post<Assessment>(assessments(courseId), payload).then((r) => r.data),
  update: (courseId: string, id: string, payload: Partial<Assessment>) => apiClient.patch<Assessment>(`${assessments(courseId)}/${id}`, payload).then((r) => r.data),
  remove: (courseId: string, id: string) => apiClient.delete(`${assessments(courseId)}/${id}`).then((r) => r.data),
  questions: (courseId: string, id: string) => apiClient.get<Question[]>(`${assessments(courseId)}/${id}/questions`).then((r) => r.data),
  addQuestion: (courseId: string, id: string, payload: QuestionPayload) => apiClient.post<Question>(`${assessments(courseId)}/${id}/questions`, payload).then((r) => r.data),
  updateQuestion: (courseId: string, id: string, qid: string, payload: QuestionPayload) => apiClient.put<Question>(`${assessments(courseId)}/${id}/questions/${qid}`, payload).then((r) => r.data),
  removeQuestion: (courseId: string, id: string, qid: string) => apiClient.delete(`${assessments(courseId)}/${id}/questions/${qid}`).then((r) => r.data),
  attempts: (courseId: string, id: string, internshipId?: string | null) =>
    apiClient.get<Attempt[]>(`${assessments(courseId)}/${id}/attempts`, { params: internshipId ? { internship_id: internshipId } : {} }).then((r) => r.data),
  recordScore: (courseId: string, id: string, studentId: string, score: number) =>
    apiClient
      .post<{ id: string }>(`${assessments(courseId)}/${id}/attempts`, { student_id: studentId })
      .then((a) => apiClient.post(`${assessments(courseId)}/${id}/attempts/${a.data.id}/submit`, { score }).then((r) => r.data)),
};

export const assessmentKeys = {
  list: (courseId: string, internshipId?: string | null) => ["learning", "assessments", courseId, internshipId ?? ""] as const,
  questions: (id: string) => ["learning", "assessment-questions", id] as const,
  attempts: (id: string, internshipId?: string | null) => ["learning", "assessment-attempts", id, internshipId ?? ""] as const,
};

// ------------------------------------------------------------------ practicals and viva (one shape)

export type EvalKind = "practicals" | "viva";
export interface EvalActivity {
  id: string;
  course_id: string;
  internship_id: string | null;
  title: string;
  exam_date: string;
  rubric?: string | null;
  panel_members?: string | null;
  total_marks: number;
  passing_marks: number;
}
export interface EvalResult {
  id: string;
  student_id: string;
  student_name: string | null;
  score: number;
  remarks: string | null;
  evaluated_at: string;
  access_status: string | null;
}
export interface EvalPayload {
  title: string;
  exam_date: string;
  total_marks: number;
  passing_marks: number;
  rubric?: string;
  panel_members?: string;
  internship_id?: string | null;
}

const evalBase = (kind: EvalKind, courseId: string) => `/examinations/courses/${courseId}/${kind}`;
export const evaluationsApi = {
  list: (kind: EvalKind, courseId: string, internshipId?: string | null) =>
    apiClient.get<EvalActivity[]>(evalBase(kind, courseId), { params: internshipId ? { internship_id: internshipId, include_course: true } : {} }).then((r) => r.data),
  create: (kind: EvalKind, courseId: string, payload: EvalPayload) => apiClient.post<EvalActivity>(evalBase(kind, courseId), payload).then((r) => r.data),
  update: (kind: EvalKind, courseId: string, id: string, payload: Partial<EvalPayload>) => apiClient.patch<EvalActivity>(`${evalBase(kind, courseId)}/${id}`, payload).then((r) => r.data),
  remove: (kind: EvalKind, courseId: string, id: string) => apiClient.delete(`${evalBase(kind, courseId)}/${id}`).then((r) => r.data),
  results: (kind: EvalKind, courseId: string, id: string, internshipId?: string | null) =>
    apiClient.get<EvalResult[]>(`${evalBase(kind, courseId)}/${id}/results`, { params: internshipId ? { internship_id: internshipId } : {} }).then((r) => r.data),
  record: (kind: EvalKind, courseId: string, id: string, payload: { student_id: string; score: number; remarks?: string }) =>
    apiClient.post<EvalResult>(`${evalBase(kind, courseId)}/${id}/results`, payload).then((r) => r.data),
  correct: (kind: EvalKind, courseId: string, id: string, studentId: string, payload: { score: number; remarks?: string }) =>
    apiClient.put<EvalResult>(`${evalBase(kind, courseId)}/${id}/results/${studentId}`, payload).then((r) => r.data),
};
export const evalKeys = {
  list: (kind: EvalKind, courseId: string, internshipId?: string | null) => ["learning", kind, courseId, internshipId ?? ""] as const,
  results: (kind: EvalKind, id: string, internshipId?: string | null) => ["learning", `${kind}-results`, id, internshipId ?? ""] as const,
};

// ------------------------------------------------------------------ discussions

export interface Thread {
  id: string;
  course_id: string;
  internship_id: string | null;
  author_name: string | null;
  title: string;
  body: string;
  is_locked: boolean;
  created_at: string;
}
export interface Reply {
  id: string;
  thread_id: string;
  author_name: string | null;
  body: string;
  created_at: string;
}
const discussions = (courseId: string) => `/lms/courses/${courseId}/discussions`;
export const discussionsApi = {
  threads: (courseId: string, internshipId?: string | null) =>
    apiClient.get<Thread[]>(discussions(courseId), { params: internshipId ? { internship_id: internshipId, include_course: true } : {} }).then((r) => r.data),
  create: (courseId: string, payload: { title: string; body: string; internship_id?: string | null }) => apiClient.post<Thread>(discussions(courseId), payload).then((r) => r.data),
  replies: (courseId: string, threadId: string) => apiClient.get<Reply[]>(`${discussions(courseId)}/${threadId}/replies`).then((r) => r.data),
  reply: (courseId: string, threadId: string, body: string) => apiClient.post<Reply>(`${discussions(courseId)}/${threadId}/replies`, { body }).then((r) => r.data),
  lock: (courseId: string, threadId: string, locked: boolean) => apiClient.put<Thread>(`${discussions(courseId)}/${threadId}/lock`, { is_locked: locked }).then((r) => r.data),
};
export const discussionKeys = {
  threads: (courseId: string, internshipId?: string | null) => ["learning", "threads", courseId, internshipId ?? ""] as const,
  replies: (threadId: string) => ["learning", "replies", threadId] as const,
};

/** Invalidates everything the workspace shows, so an edit made in one tab (or on the other page) is on screen everywhere. */
export function useRefreshLearning() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: learningKeys.all });
}

