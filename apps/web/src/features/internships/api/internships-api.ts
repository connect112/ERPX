import { apiClient } from "@/api/client";
import type {
  InternshipApplicationStatus,
  InternshipPostingStatus,
  InternshipStatus,
} from "@/features/internships/schemas/posting-schemas";

export interface InternshipPostingPublic {
  id: string;
  organization_id: string;
  company_id: string;
  title: string;
  description: string | null;
  duration_months: number | null;
  stipend: number | null;
  location: string | null;
  required_skills: string | null;
  application_deadline: string | null;
  status: InternshipPostingStatus;
  created_at: string;
}

export interface InternshipPostingListResponse {
  items: InternshipPostingPublic[];
  total: number;
}

export interface InternshipPostingListParams {
  status?: InternshipPostingStatus;
  company_id?: string;
  skip?: number;
  limit?: number;
}

export interface InternshipPostingCreatePayload {
  company_id: string;
  title: string;
  description?: string;
  duration_months?: number;
  stipend?: number;
  location?: string;
  required_skills?: string;
  application_deadline?: string;
}

export type InternshipPostingUpdatePayload = Partial<Omit<InternshipPostingCreatePayload, "company_id">>;

export interface InternshipApplicationPublic {
  id: string;
  internship_posting_id: string;
  student_id: string;
  applied_at: string;
  cover_letter: string | null;
  status: InternshipApplicationStatus;
  notes: string | null;
  created_at: string;
}

export interface InternshipPublic {
  id: string;
  organization_id: string;
  application_id: string;
  internship_posting_id: string;
  student_id: string;
  mentor_employee_id: string | null;
  start_date: string;
  end_date: string | null;
  stipend: number | null;
  status: InternshipStatus;
  feedback: string | null;
  created_at: string;
}

export interface InternshipListResponse {
  items: InternshipPublic[];
  total: number;
}

export const internshipsApi = {
  listPostings: (params: InternshipPostingListParams) =>
    apiClient.get<InternshipPostingListResponse>("/internships/postings", { params }).then((r) => r.data),

  getPosting: (id: string) =>
    apiClient.get<InternshipPostingPublic>(`/internships/postings/${id}`).then((r) => r.data),

  createPosting: (payload: InternshipPostingCreatePayload) =>
    apiClient.post<InternshipPostingPublic>("/internships/postings", payload).then((r) => r.data),

  updatePosting: (id: string, payload: InternshipPostingUpdatePayload) =>
    apiClient.patch<InternshipPostingPublic>(`/internships/postings/${id}`, payload).then((r) => r.data),

  changePostingStatus: (id: string, status: InternshipPostingStatus) =>
    apiClient
      .post<InternshipPostingPublic>(`/internships/postings/${id}/status`, { status })
      .then((r) => r.data),

  listPostingApplications: (id: string) =>
    apiClient
      .get<InternshipApplicationPublic[]>(`/internships/postings/${id}/applications`)
      .then((r) => r.data),

  changeApplicationStatus: (id: string, status: InternshipApplicationStatus, notes?: string) =>
    apiClient
      .post<InternshipApplicationPublic>(`/internships/applications/${id}/status`, { status, notes })
      .then((r) => r.data),

  listInternships: (params: { skip?: number; limit?: number }) =>
    apiClient.get<InternshipListResponse>("/internships/internships", { params }).then((r) => r.data),

  updateInternship: (
    id: string,
    payload: { mentor_employee_id?: string; end_date?: string; stipend?: number; feedback?: string }
  ) => apiClient.patch<InternshipPublic>(`/internships/internships/${id}`, payload).then((r) => r.data),

  changeInternshipStatus: (id: string, status: InternshipStatus) =>
    apiClient
      .post<InternshipPublic>(`/internships/internships/${id}/status`, { status })
      .then((r) => r.data),
};
