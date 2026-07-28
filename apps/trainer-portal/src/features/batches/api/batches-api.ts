import { apiClient } from "@/api/client";

export interface BatchPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  course_id: string;
  trainer_id: string | null;
  name: string;
  code: string;
  status: "upcoming" | "ongoing" | "completed" | "cancelled";
  capacity: number | null;
  start_date: string;
  end_date: string | null;
  created_at: string;
  course_title: string;
}

export interface AssignmentPublic {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  due_date: string | null;
  max_score: number;
  created_at: string;
}

export interface SubmissionPublic {
  id: string;
  assignment_id: string;
  student_id: string;
  student_name: string;
  content_url: string | null;
  content_text: string | null;
  submitted_at: string;
  status: "submitted" | "graded" | "late";
  score: number | null;
  feedback: string | null;
  created_at: string;
}

export const batchesApi = {
  myBatches: () => apiClient.get<BatchPublic[]>("/batches/me").then((r) => r.data),

  listAssignments: (courseId: string) =>
    apiClient
      .get<AssignmentPublic[]>(`/lms/courses/${courseId}/assignments/me`)
      .then((r) => r.data),

  listSubmissions: (courseId: string, assignmentId: string) =>
    apiClient
      .get<SubmissionPublic[]>(
        `/lms/courses/${courseId}/assignments/${assignmentId}/submissions/me`
      )
      .then((r) => r.data),

  gradeSubmission: (
    courseId: string,
    assignmentId: string,
    submissionId: string,
    payload: { score: number; feedback?: string }
  ) =>
    apiClient
      .post<SubmissionPublic>(
        `/lms/courses/${courseId}/assignments/${assignmentId}/submissions/${submissionId}/grade/me`,
        payload
      )
      .then((r) => r.data),
};
