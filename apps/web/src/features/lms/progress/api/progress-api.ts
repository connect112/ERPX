import { apiClient } from "@/api/client";

export interface CourseProgressResponse {
  student_id: string;
  course_id: string;
  total_lessons: number;
  completed_lessons: number;
  percent_complete: number;
}

export interface LessonProgressPublic {
  id: string;
  student_id: string;
  lesson_id: string;
  completed_at: string;
}

export const progressApi = {
  getCourseProgress: (studentId: string, courseId: string) =>
    apiClient
      .get<CourseProgressResponse>(`/lms/progress/${studentId}/course/${courseId}`)
      .then((r) => r.data),

  markComplete: (studentId: string, lessonId: string) =>
    apiClient
      .post<LessonProgressPublic>("/lms/progress/complete", { student_id: studentId, lesson_id: lessonId })
      .then((r) => r.data),

  unmarkComplete: (studentId: string, lessonId: string) =>
    apiClient
      .post("/lms/progress/uncomplete", { student_id: studentId, lesson_id: lessonId })
      .then((r) => r.data),
};
