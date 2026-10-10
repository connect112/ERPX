import axios from "axios";

import { apiClient } from "@/api/client";

export type SubmissionStatus = "submitted" | "graded" | "late";

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
  content_url: string | null;
  content_text: string | null;
  submitted_at: string;
  status: SubmissionStatus;
  score: number | null;
  feedback: string | null;
  created_at: string;
}

export interface MySubmissionPayload {
  content_url?: string;
  content_text?: string;
}

const base = (courseId: string) => `/lms/courses/${courseId}/assignments`;

export const assignmentsApi = {
  list: (courseId: string) =>
    apiClient.get<AssignmentPublic[]>(base(courseId)).then((r) => r.data),

  // Returns null (not a thrown error) when the student hasn't submitted yet
  // — the backend 404s, which callers would otherwise have to catch
  // individually; centralizing that here keeps the hook/component code
  // simple (see assignments-hooks.ts's use of this).
  mySubmission: async (courseId: string, assignmentId: string): Promise<SubmissionPublic | null> => {
    try {
      const response = await apiClient.get<SubmissionPublic>(
        `${base(courseId)}/${assignmentId}/submissions/mine`
      );
      return response.data;
    } catch (error: unknown) {
      if (axios.isAxiosError(error) && error.response?.status === 404) return null;
      throw error;
    }
  },

  submitMine: (courseId: string, assignmentId: string, payload: MySubmissionPayload) =>
    apiClient
      .post<SubmissionPublic>(`${base(courseId)}/${assignmentId}/submissions/mine`, payload)
      .then((r) => r.data),
};
