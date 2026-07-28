import { apiClient } from "@/api/client";

export interface EnrollmentPublic {
  id: string;
  student_id: string;
  course_id: string;
  enrolled_on: string;
  status: "active" | "completed" | "dropped" | "on_hold";
  created_at: string;
}

export interface CoursePublic {
  id: string;
  organization_id: string;
  category_id: string | null;
  title: string;
  slug: string;
  short_description: string | null;
  description: string | null;
  thumbnail_url: string | null;
  level: "beginner" | "intermediate" | "advanced";
  duration_hours: number | null;
  price: number;
  is_published: boolean;
  created_at: string;
}

export interface ChapterPublic {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  order_index: number;
}

export interface LessonPublic {
  id: string;
  chapter_id: string;
  title: string;
  content_type: string;
  order_index: number;
}

export interface CourseProgressResponse {
  student_id: string;
  course_id: string;
  total_lessons: number;
  completed_lessons: number;
  percent_complete: number;
  completed_lesson_ids: string[];
}

export const coursesApi = {
  myEnrollments: () => apiClient.get<EnrollmentPublic[]>("/lms/enrollment/me").then((r) => r.data),

  getCourse: (id: string) => apiClient.get<CoursePublic>(`/courses/${id}/me`).then((r) => r.data),

  listChapters: (courseId: string) =>
    apiClient.get<ChapterPublic[]>(`/courses/${courseId}/chapters/me`).then((r) => r.data),

  listLessons: (courseId: string, chapterId: string) =>
    apiClient
      .get<LessonPublic[]>(`/courses/${courseId}/chapters/${chapterId}/lessons/me`)
      .then((r) => r.data),

  myProgress: (courseId: string) =>
    apiClient
      .get<CourseProgressResponse>(`/lms/progress/me/course/${courseId}`)
      .then((r) => r.data),

  markLessonComplete: (lessonId: string) =>
    apiClient.post(`/lms/progress/me/complete/${lessonId}`).then((r) => r.data),
};
