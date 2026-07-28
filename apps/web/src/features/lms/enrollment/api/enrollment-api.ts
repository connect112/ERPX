import { apiClient } from "@/api/client";
import type { EnrollmentStatus } from "@/features/lms/enrollment/schemas/enrollment-schemas";

export interface EnrollmentPublic {
  id: string;
  student_id: string;
  course_id: string;
  enrolled_on: string;
  status: EnrollmentStatus;
  created_at: string;
}

export interface EnrollmentCreatePayload {
  student_id: string;
  course_id: string;
  enrolled_on?: string;
}

export const enrollmentApi = {
  listForStudent: (studentId: string) =>
    apiClient
      .get<EnrollmentPublic[]>(`/lms/enrollment/by-student/${studentId}`)
      .then((r) => r.data),

  listForCourse: (courseId: string) =>
    apiClient
      .get<EnrollmentPublic[]>(`/lms/enrollment/by-course/${courseId}`)
      .then((r) => r.data),

  create: (payload: EnrollmentCreatePayload) =>
    apiClient.post<EnrollmentPublic>("/lms/enrollment", payload).then((r) => r.data),

  changeStatus: (enrollmentId: string, status: EnrollmentStatus) =>
    apiClient
      .post<EnrollmentPublic>(`/lms/enrollment/${enrollmentId}/status`, { status })
      .then((r) => r.data),
};
