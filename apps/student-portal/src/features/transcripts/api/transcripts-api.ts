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

export interface CourseResult {
  student_id: string;
  course_id: string;
  components: ComponentResult[];
  overall_score: number;
  overall_total: number;
  overall_percentage: number;
  overall_status: "pass" | "fail" | "incomplete";
}

export interface CourseTranscriptEntry {
  course_id: string;
  course_title: string;
  enrollment_status: "active" | "completed" | "dropped";
  enrolled_on: string;
  percent_complete: number;
  result: CourseResult | null;
  certificate_number: string | null;
  certificate_issued_at: string | null;
}

export interface TranscriptResponse {
  student_id: string;
  student_code: string;
  student_name: string;
  courses: CourseTranscriptEntry[];
  total_courses: number;
  completed_courses: number;
  certificates_earned: number;
}

export const transcriptsApi = {
  myTranscript: () => apiClient.get<TranscriptResponse>("/lms/transcripts/me").then((r) => r.data),
};
