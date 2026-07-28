import { apiClient } from "@/api/client";

export interface BookmarkPublic {
  id: string;
  lesson_id: string;
  lesson_title: string;
  course_id: string;
  course_title: string;
  created_at: string;
}

export const bookmarksApi = {
  myBookmarks: () => apiClient.get<BookmarkPublic[]>("/lms/bookmarks/me").then((r) => r.data),

  addBookmark: (lessonId: string) =>
    apiClient.post(`/lms/bookmarks/me/${lessonId}`).then((r) => r.data),

  removeBookmark: (lessonId: string) =>
    apiClient.delete(`/lms/bookmarks/me/${lessonId}`).then((r) => r.data),
};
