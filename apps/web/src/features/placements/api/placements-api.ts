import { apiClient } from "@/api/client";
import type {
  ApplicationStatus,
  JobType,
  PostingStatus,
} from "@/features/placements/schemas/posting-schemas";

export interface CompanyPublic {
  id: string;
  organization_id: string;
  name: string;
  industry: string | null;
  website: string | null;
  contact_person_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  notes: string | null;
  created_at: string;
}

export interface CompanyListResponse {
  items: CompanyPublic[];
  total: number;
}

export interface CompanyPayload {
  name: string;
  industry?: string;
  website?: string;
  contact_person_name?: string;
  contact_email?: string;
  contact_phone?: string;
  notes?: string;
}

export interface JobPostingPublic {
  id: string;
  organization_id: string;
  company_id: string;
  title: string;
  description: string | null;
  job_type: JobType;
  location: string | null;
  salary_min: number | null;
  salary_max: number | null;
  required_skills: string | null;
  application_deadline: string | null;
  status: PostingStatus;
  // Job-aggregation pipeline attribution fields. "manual" for every
  // staff-created posting (unchanged existing behavior).
  source: string;
  source_url: string | null;
  last_seen_at: string | null;
  created_at: string;
}

export interface JobPostingListResponse {
  items: JobPostingPublic[];
  total: number;
}

export interface JobPostingListParams {
  status?: PostingStatus;
  company_id?: string;
  skip?: number;
  limit?: number;
}

export interface JobPostingCreatePayload {
  company_id: string;
  title: string;
  description?: string;
  job_type: JobType;
  location?: string;
  salary_min?: number;
  salary_max?: number;
  required_skills?: string;
  application_deadline?: string;
}

export type JobPostingUpdatePayload = Partial<Omit<JobPostingCreatePayload, "company_id">>;

export interface ApplicationPublic {
  id: string;
  job_posting_id: string;
  student_id: string;
  applied_at: string;
  cover_letter: string | null;
  status: ApplicationStatus;
  notes: string | null;
  created_at: string;
}

export const placementsApi = {
  listCompanies: (params: { skip?: number; limit?: number }) =>
    apiClient.get<CompanyListResponse>("/placements/companies", { params }).then((r) => r.data),

  createCompany: (payload: CompanyPayload) =>
    apiClient.post<CompanyPublic>("/placements/companies", payload).then((r) => r.data),

  updateCompany: (id: string, payload: Partial<CompanyPayload>) =>
    apiClient.patch<CompanyPublic>(`/placements/companies/${id}`, payload).then((r) => r.data),

  deleteCompany: (id: string) =>
    apiClient.delete(`/placements/companies/${id}`).then((r) => r.data),

  listPostings: (params: JobPostingListParams) =>
    apiClient.get<JobPostingListResponse>("/placements/postings", { params }).then((r) => r.data),

  getPosting: (id: string) =>
    apiClient.get<JobPostingPublic>(`/placements/postings/${id}`).then((r) => r.data),

  createPosting: (payload: JobPostingCreatePayload) =>
    apiClient.post<JobPostingPublic>("/placements/postings", payload).then((r) => r.data),

  updatePosting: (id: string, payload: JobPostingUpdatePayload) =>
    apiClient.patch<JobPostingPublic>(`/placements/postings/${id}`, payload).then((r) => r.data),

  changePostingStatus: (id: string, status: PostingStatus) =>
    apiClient.post<JobPostingPublic>(`/placements/postings/${id}/status`, { status }).then((r) => r.data),

  listPostingApplications: (id: string) =>
    apiClient.get<ApplicationPublic[]>(`/placements/postings/${id}/applications`).then((r) => r.data),

  changeApplicationStatus: (id: string, status: ApplicationStatus, notes?: string) =>
    apiClient
      .post<ApplicationPublic>(`/placements/applications/${id}/status`, { status, notes })
      .then((r) => r.data),
};
