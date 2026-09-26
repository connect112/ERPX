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
  // Job-aggregation pipeline attribution fields. "manual" for every
  // staff-created posting (unchanged existing behavior).
  source: string;
  source_url: string | null;
  last_seen_at: string | null;
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

export const placementsApi = {
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
