import { apiClient } from "@/api/client";
import type { Gender, StudentStatus } from "@/features/students/schemas/student-schemas";

export interface StudentPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  admission_id: string | null;
  user_id: string | null;
  student_code: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  gender: Gender | null;
  date_of_birth: string | null;
  guardian_name: string | null;
  guardian_phone: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  course_name: string;
  batch_name: string | null;
  enrollment_date: string;
  status: StudentStatus;
  notes: string | null;
  created_at: string;
}

export interface StudentListResponse {
  items: StudentPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface StudentListParams {
  status?: StudentStatus;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface StudentCreatePayload {
  branch_id?: string;
  full_name: string;
  email?: string;
  phone?: string;
  gender?: Gender;
  date_of_birth?: string;
  guardian_name?: string;
  guardian_phone?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  course_name: string;
  batch_name?: string;
  enrollment_date: string;
  notes?: string;
}

export type StudentUpdatePayload = Partial<Omit<StudentCreatePayload, "course_name" | "enrollment_date">>;

export interface StudentFromAdmissionPayload {
  branch_id?: string;
  enrollment_date?: string;
}

export const studentsApi = {
  list: (params: StudentListParams) =>
    apiClient.get<StudentListResponse>("/students", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<StudentPublic>(`/students/${id}`).then((r) => r.data),

  create: (payload: StudentCreatePayload) =>
    apiClient.post<StudentPublic>("/students", payload).then((r) => r.data),

  update: (id: string, payload: StudentUpdatePayload) =>
    apiClient.patch<StudentPublic>(`/students/${id}`, payload).then((r) => r.data),

  changeStatus: (id: string, status: StudentStatus, notes?: string) =>
    apiClient.post<StudentPublic>(`/students/${id}/status`, { status, notes }).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/students/${id}`).then((r) => r.data),

  createFromAdmission: (admissionId: string, payload: StudentFromAdmissionPayload) =>
    apiClient
      .post<StudentPublic>(`/students/from-admission/${admissionId}`, payload)
      .then((r) => r.data),
};
