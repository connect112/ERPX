import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

/**
 * The instructor's Learning workspace, in the portal. It talks to the same endpoints as the administrator site (the server decides what an
 * instructor may do: only their own internships, only during their window, never delete), so both show and change the very same records.
 */

export interface TabDef { key: string; label: string }
export interface InternshipRef { id: string; title: string; status: string; can_view: boolean; can_manage: boolean; can_delete: boolean }
export interface LearningContext {
  tabs: TabDef[];
  course: { id: string; title: string; course_type: string; is_published: boolean } | null;
  internships: InternshipRef[];
  course_caps: Record<string, boolean>;
}
export interface EnrollmentRow {
  selection_id: string;
  lms_student_id: string | null;
  name: string;
  email: string;
  lms_status: string;
  enrollment_status: string | null;
  provenance: string | null;
  progress_percent: number | null;
}
export interface ResultRow {
  kind: string;
  scope: string;
  activity_id: string;
  activity_title: string;
  student_key: string;
  student_name: string;
  access_status: string | null;
  state: string;
  completed: boolean;
  score: number | null;
  total_marks: number | null;
  percent: number | null;
}
export interface SubmissionRow {
  selection_id: string;
  student_name: string;
  student_email: string;
  access_status: string;
  submitted: boolean;
  submitted_at: string | null;
  is_late: boolean;
  note: string | null;
  score: number | null;
  feedback: string | null;
  reviewed_at: string | null;
  files: { id: string; filename: string }[];
}
export interface Assignment { id: string; title: string; status: string; max_marks: number; deadline_at: string | null; submitted_count: number; graded_count: number; enrolled_count: number }
export interface ExamSummary { id: string; title: string; status: string; question_count: number; attendee_count: number; submitted_count: number; average_percent: number | null }
export interface ExamResult { selection_id: string; student_name: string; state: string; score: number | null; total_marks: number | null; percent: number | null; access_status: string }
export interface Project { id: string; title: string; status: string; max_marks: number }
export interface ProjectRow { selection_id: string; student_name: string; access_status: string; project_id: string | null; project_title: string | null; submitted: boolean; method: string | null; repository_url: string | null; submitted_at: string | null }
export interface Assessment { id: string; internship_id: string | null; title: string; assessment_type: string; total_marks: number; passing_marks: number; duration_minutes: number | null; is_published: boolean }
export interface Question { id: string; text: string; options: string[]; correct_indices: number[]; marks: number; allow_multiple: boolean }
export interface Attempt { id: string; student_name: string | null; score: number | null; total_marks: number | null; status: string; access_status: string | null }
export interface EvalActivity { id: string; internship_id: string | null; title: string; exam_date: string; total_marks: number; passing_marks: number; rubric?: string | null; panel_members?: string | null }
export interface EvalResult { id: string; student_id: string; student_name: string | null; score: number; remarks: string | null; access_status: string | null }
export interface Thread { id: string; internship_id: string | null; author_name: string | null; title: string; body: string; is_locked: boolean; created_at: string }
export interface Reply { id: string; author_name: string | null; body: string }
export interface Chapter { id: string; title: string; order_index: number; description: string | null }
export interface Lesson { id: string; title: string; content_type: string; order_index: number }

const I = (id: string) => `/our-internships/${id}`;
const C = (id: string) => `/lms/courses/${id}`;
const E = (kind: string, id: string) => `/examinations/courses/${id}/${kind}`;

export const learningApi = {
  context: (internshipId: string) => apiClient.get<LearningContext>("/learning/context", { params: { internship_id: internshipId } }).then((r) => r.data),
  enrollments: (internshipId: string) => apiClient.get<{ rows: EnrollmentRow[] }>("/learning/enrollments", { params: { internship_id: internshipId } }).then((r) => r.data.rows),
  results: (internshipId: string, kind?: string) => apiClient.get<{ rows: ResultRow[] }>("/learning/results", { params: { internship_id: internshipId, kind: kind || undefined } }).then((r) => r.data.rows),
  chapters: (courseId: string) => apiClient.get<Chapter[]>(`/courses/${courseId}/chapters`).then((r) => r.data),
  lessons: (courseId: string, chapterId: string) => apiClient.get<Lesson[]>(`/courses/${courseId}/chapters/${chapterId}/lessons`).then((r) => r.data),
  assignments: (id: string) => apiClient.get<Assignment[]>(`${I(id)}/assignments`).then((r) => r.data),
  submissions: (id: string, aid: string) => apiClient.get<SubmissionRow[]>(`${I(id)}/assignments/${aid}/submissions`).then((r) => r.data),
  grade: (id: string, aid: string, sel: string, body: { score: number; feedback?: string }) => apiClient.put(`${I(id)}/assignments/${aid}/submissions/${sel}/grade`, body).then((r) => r.data),
  exams: (id: string) => apiClient.get<ExamSummary[]>(`${I(id)}/exams`).then((r) => r.data),
  examResults: (id: string, eid: string) => apiClient.get<ExamResult[]>(`${I(id)}/exams/${eid}/results`).then((r) => r.data),
  projects: (id: string) => apiClient.get<Project[]>(`${I(id)}/projects`).then((r) => r.data),
  projectRows: (id: string) => apiClient.get<ProjectRow[]>(`${I(id)}/project-selections`).then((r) => r.data),
  finalMarks: (id: string, pid: string, sel: string, body: { final_marks: number; feedback?: string }) => apiClient.put(`${I(id)}/projects/${pid}/submissions/${sel}/final`, body).then((r) => r.data),
  assessments: (courseId: string, internshipId: string) => apiClient.get<Assessment[]>(`${C(courseId)}/assessments`, { params: { internship_id: internshipId, include_course: true } }).then((r) => r.data),
  createAssessment: (courseId: string, body: object) => apiClient.post<Assessment>(`${C(courseId)}/assessments`, body).then((r) => r.data),
  setPublished: (courseId: string, id: string, v: boolean) => apiClient.patch(`${C(courseId)}/assessments/${id}`, { is_published: v }).then((r) => r.data),
  questions: (courseId: string, id: string) => apiClient.get<Question[]>(`${C(courseId)}/assessments/${id}/questions`).then((r) => r.data),
  addQuestion: (courseId: string, id: string, body: object) => apiClient.post<Question>(`${C(courseId)}/assessments/${id}/questions`, body).then((r) => r.data),
  attempts: (courseId: string, id: string, internshipId: string) => apiClient.get<Attempt[]>(`${C(courseId)}/assessments/${id}/attempts`, { params: { internship_id: internshipId } }).then((r) => r.data),
  evals: (kind: string, courseId: string, internshipId: string) => apiClient.get<EvalActivity[]>(E(kind, courseId), { params: { internship_id: internshipId, include_course: true } }).then((r) => r.data),
  createEval: (kind: string, courseId: string, body: object) => apiClient.post<EvalActivity>(E(kind, courseId), body).then((r) => r.data),
  evalResults: (kind: string, courseId: string, id: string, internshipId: string) => apiClient.get<EvalResult[]>(`${E(kind, courseId)}/${id}/results`, { params: { internship_id: internshipId } }).then((r) => r.data),
  recordEval: (kind: string, courseId: string, id: string, body: object) => apiClient.post(`${E(kind, courseId)}/${id}/results`, body).then((r) => r.data),
  correctEval: (kind: string, courseId: string, id: string, studentId: string, body: object) => apiClient.put(`${E(kind, courseId)}/${id}/results/${studentId}`, body).then((r) => r.data),
  threads: (courseId: string, internshipId: string) => apiClient.get<Thread[]>(`${C(courseId)}/discussions`, { params: { internship_id: internshipId, include_course: true } }).then((r) => r.data),
  createThread: (courseId: string, body: object) => apiClient.post<Thread>(`${C(courseId)}/discussions`, body).then((r) => r.data),
  replies: (courseId: string, tid: string) => apiClient.get<Reply[]>(`${C(courseId)}/discussions/${tid}/replies`).then((r) => r.data),
  reply: (courseId: string, tid: string, body: string) => apiClient.post(`${C(courseId)}/discussions/${tid}/replies`, { body }).then((r) => r.data),
};

export const key = (...parts: (string | undefined)[]) => ["trainer-learning", ...parts] as const;

export function useQ<T>(k: readonly unknown[], fn: () => Promise<T>, enabled = true) {
  return useQuery({ queryKey: k, queryFn: fn, enabled });
}
export function useAct<A>(fn: (a: A) => Promise<unknown>, after?: () => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["trainer-learning"] });
      after?.();
    },
  });
}

export function errorText(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error;
  return data?.message ?? fallback;
}
