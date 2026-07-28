import { apiClient } from "@/api/client";

export interface ThreadPublic {
  id: string;
  course_id: string;
  created_by_user_id: string | null;
  title: string;
  body: string;
  is_locked: boolean;
  created_at: string;
}

export interface ReplyPublic {
  id: string;
  thread_id: string;
  created_by_user_id: string | null;
  body: string;
  created_at: string;
}

const base = (courseId: string) => `/lms/courses/${courseId}/discussions`;

export const discussionsApi = {
  listThreads: (courseId: string) =>
    apiClient.get<ThreadPublic[]>(base(courseId)).then((r) => r.data),

  createThread: (courseId: string, payload: { title: string; body: string }) =>
    apiClient.post<ThreadPublic>(base(courseId), payload).then((r) => r.data),

  listReplies: (courseId: string, threadId: string) =>
    apiClient.get<ReplyPublic[]>(`${base(courseId)}/${threadId}/replies`).then((r) => r.data),

  reply: (courseId: string, threadId: string, body: string) =>
    apiClient
      .post<ReplyPublic>(`${base(courseId)}/${threadId}/replies`, { body })
      .then((r) => r.data),
};
