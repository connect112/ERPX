import { apiClient } from "@/api/client";

export interface CertificationPublic {
  id: string;
  student_id: string;
  track_name: string;
  certificate_number: string;
  points_at_issuance: number;
  issued_at: string;
}

export interface CertificationVerificationResponse {
  valid: boolean;
  certificate_number: string;
  student_name: string | null;
  track_name: string | null;
  points_at_issuance: number | null;
  issued_at: string | null;
}

export const certificationsApi = {
  listForStudent: (studentId: string) =>
    apiClient
      .get<CertificationPublic[]>(`/pentrix/certifications/students/${studentId}`)
      .then((r) => r.data),

  issue: (studentId: string, trackName: string, minimumPoints: number, force = false) =>
    apiClient
      .post<CertificationPublic>("/pentrix/certifications", {
        student_id: studentId,
        track_name: trackName,
        minimum_points: minimumPoints,
        force,
      })
      .then((r) => r.data),

  verify: (certificateNumber: string) =>
    apiClient
      .get<CertificationVerificationResponse>(`/pentrix/certifications/verify/${certificateNumber}`)
      .then((r) => r.data),
};
