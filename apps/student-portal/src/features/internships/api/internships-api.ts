import { apiClient } from "@/api/client";

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
  status: "draft" | "open" | "closed";
  created_at: string;
}

export type InternshipApplicationStatus = "applied" | "shortlisted" | "selected" | "rejected" | "withdrawn";

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
  status: "ongoing" | "completed" | "terminated";
  feedback: string | null;
  created_at: string;
}

export const internshipsApi = {
  browsePostings: () =>
    apiClient.get<InternshipPostingPublic[]>("/internships/postings/me").then((r) => r.data),

  apply: (postingId: string, coverLetter?: string) =>
    apiClient
      .post<InternshipApplicationPublic>(`/internships/postings/${postingId}/apply/me`, {
        cover_letter: coverLetter,
      })
      .then((r) => r.data),

  myApplications: () =>
    apiClient.get<InternshipApplicationPublic[]>("/internships/applications/me").then((r) => r.data),

  withdraw: (applicationId: string) =>
    apiClient
      .post<InternshipApplicationPublic>(`/internships/applications/${applicationId}/withdraw/me`)
      .then((r) => r.data),

  myInternships: () => apiClient.get<InternshipPublic[]>("/internships/me").then((r) => r.data),
};
