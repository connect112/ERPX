import { apiClient } from "@/api/client";

export interface ComponentResult {
  component_type: string;
  component_id: string;
  title: string;
  score: number | null;
  total_marks: number;
  passing_marks: number;
  passed: boolean | null;
}

export interface StudentCourseResultResponse {
  student_id: string;
  course_id: string;
  components: ComponentResult[];
  overall_score: number;
  overall_total: number;
  overall_percentage: number;
  overall_status: string;
}

export const resultsApi = {
  getForStudentCourse: (studentId: string, courseId: string) =>
    apiClient
      .get<StudentCourseResultResponse>(`/examinations/results/${studentId}/course/${courseId}`)
      .then((r) => r.data),
};
