import { apiClient } from "@/api/client";

export type JobType = "full_time" | "part_time" | "internship" | "contract";

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
  status: "draft" | "open" | "closed";
  created_at: string;
}

export type PlacementApplicationStatus =
  | "applied"
  | "shortlisted"
  | "interview_scheduled"
  | "offered"
  | "rejected"
  | "withdrawn";

export interface ApplicationPublic {
  id: string;
  job_posting_id: string;
  student_id: string;
  applied_at: string;
  cover_letter: string | null;
  status: PlacementApplicationStatus;
  notes: string | null;
  created_at: string;
}

/** A job found on an outside job site: Apply opens the original page. */
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
}

export interface ExternalJobList {
  items: ExternalJob[];
  total: number;
  skip: number;
  limit: number;
}

export const placementsApi = {
  externalJobs: (params: { q?: string; fresher_only?: boolean; skip?: number; limit?: number }) =>
    apiClient.get<ExternalJobList>("/placements/external/me", { params }).then((r) => r.data),

  browsePostings: () => apiClient.get<JobPostingPublic[]>("/placements/postings/me").then((r) => r.data),

  apply: (postingId: string, coverLetter?: string) =>
    apiClient
      .post<ApplicationPublic>(`/placements/postings/${postingId}/apply/me`, {
        cover_letter: coverLetter,
      })
      .then((r) => r.data),

  myApplications: () =>
    apiClient.get<ApplicationPublic[]>("/placements/applications/me").then((r) => r.data),

  withdraw: (applicationId: string) =>
    apiClient
      .post<ApplicationPublic>(`/placements/applications/${applicationId}/withdraw/me`)
      .then((r) => r.data),
};
