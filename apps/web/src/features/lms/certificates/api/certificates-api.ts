import { apiClient } from "@/api/client";

export interface CertificatePublic {
  id: string;
  student_id: string;
  course_id: string;
  certificate_number: string;
  issued_at: string;
}

export interface CertificateVerificationResponse {
  valid: boolean;
  certificate_number: string;
  student_name: string | null;
  course_title: string | null;
  issued_at: string | null;
}

export const certificatesApi = {
  listForStudent: (studentId: string) =>
    apiClient
      .get<CertificatePublic[]>(`/lms/certificates/by-student/${studentId}`)
      .then((r) => r.data),

  issue: (studentId: string, courseId: string, force = false) =>
    apiClient
      .post<CertificatePublic>("/lms/certificates", { student_id: studentId, course_id: courseId, force })
      .then((r) => r.data),

  verify: (certificateNumber: string) =>
    apiClient
      .get<CertificateVerificationResponse>(`/lms/certificates/verify/${certificateNumber}`)
      .then((r) => r.data),
};
