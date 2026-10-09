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

/** A job found on an outside job site. Students apply on the original page (`url`). */
export interface ExternalJob {
  id: string;
  source: string;
  title: string;
  company_name: string;
  location: string | null;
  remote: boolean;
  job_type: string | null;
  summary: string | null;
  url: string;
  tags: string[];
  posted_at: string | null;
  salary_text: string | null;
  fresher_friendly: boolean;
  hidden: boolean;
}

export interface ExternalJobList {
  items: ExternalJob[];
  total: number;
  skip: number;
  limit: number;
}

export interface JobSourceStatus {
  name: string;
  label: string;
  enabled: boolean;
  /** False = the server has no API key for this source yet. */
  configured: boolean;
  last_fetch_at: string | null;
  last_error: string | null;
  matched: number | null;
}

export interface JobFeedSettings {
  keywords: string[];
  /** Only jobs in India, or remote and open to India. */
  india_only: boolean;
  /** Company career pages read, by hiring system: { greenhouse: [...], lever: [...] }. */
  boards: Record<string, string[]>;
  /** A refresh is running in the background. */
  refreshing: boolean;
  sources: JobSourceStatus[];
}

export interface JobFeedSettingsUpdate {
  keywords?: string[];
  india_only?: boolean;
  boards?: Record<string, string[]>;
  sources?: Record<string, boolean>;
}

export interface JobFeedRefreshResult {
  message: string;
  sources: Record<string, { fetched?: number; matched?: number; new?: number; skipped?: string; error?: string }>;
}

export const placementsApi = {
  listExternalJobs: (params: { q?: string; source?: string; include_hidden?: boolean; skip?: number; limit?: number }) =>
    apiClient.get<ExternalJobList>("/placements/external", { params }).then((r) => r.data),

  jobFeedSettings: () => apiClient.get<JobFeedSettings>("/placements/external/settings").then((r) => r.data),

  updateJobFeedSettings: (payload: JobFeedSettingsUpdate) =>
    apiClient.put<JobFeedSettings>("/placements/external/settings", payload).then((r) => r.data),

  refreshJobFeed: () => apiClient.post<JobFeedRefreshResult>("/placements/external/refresh").then((r) => r.data),

  setExternalJobHidden: (id: string, hidden: boolean) =>
    apiClient.post<ExternalJob>(`/placements/external/${id}/hidden`, { hidden }).then((r) => r.data),

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
