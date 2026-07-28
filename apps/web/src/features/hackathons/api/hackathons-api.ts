import { apiClient } from "@/api/client";
import type { HackathonStatus } from "@/features/hackathons/schemas/hackathon-schemas";

export interface HackathonPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  code: string;
  title: string;
  theme: string | null;
  description: string | null;
  registration_deadline: string;
  start_date: string;
  end_date: string;
  max_team_size: number;
  prize_pool: number | null;
  status: HackathonStatus;
  created_at: string;
}

export interface HackathonListResponse {
  items: HackathonPublic[];
  total: number;
}

export interface HackathonListParams {
  status?: HackathonStatus;
  skip?: number;
  limit?: number;
}

export interface HackathonCreatePayload {
  code: string;
  title: string;
  theme?: string;
  description?: string;
  registration_deadline: string;
  start_date: string;
  end_date: string;
  max_team_size?: number;
  prize_pool?: number;
}

export interface HackathonUpdatePayload {
  title?: string;
  theme?: string;
  description?: string;
  registration_deadline?: string;
  start_date?: string;
  end_date?: string;
  max_team_size?: number;
  prize_pool?: number;
}

export interface TeamPublic {
  id: string;
  hackathon_id: string;
  created_by_student_id: string;
  name: string;
  created_at: string;
}

export interface SubmissionPublic {
  id: string;
  team_id: string;
  title: string;
  description: string | null;
  repo_url: string | null;
  demo_url: string | null;
  submitted_at: string;
  score: number | null;
  feedback: string | null;
  created_at: string;
}

export const hackathonsApi = {
  list: (params: HackathonListParams) =>
    apiClient.get<HackathonListResponse>("/hackathons", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<HackathonPublic>(`/hackathons/${id}`).then((r) => r.data),

  create: (payload: HackathonCreatePayload) =>
    apiClient.post<HackathonPublic>("/hackathons", payload).then((r) => r.data),

  update: (id: string, payload: HackathonUpdatePayload) =>
    apiClient.patch<HackathonPublic>(`/hackathons/${id}`, payload).then((r) => r.data),

  changeStatus: (id: string, status: HackathonStatus) =>
    apiClient.post<HackathonPublic>(`/hackathons/${id}/status`, { status }).then((r) => r.data),

  listTeams: (id: string) => apiClient.get<TeamPublic[]>(`/hackathons/${id}/teams`).then((r) => r.data),

  listSubmissions: (id: string) =>
    apiClient.get<SubmissionPublic[]>(`/hackathons/${id}/submissions`).then((r) => r.data),

  gradeSubmission: (submissionId: string, score: number, feedback?: string) =>
    apiClient
      .post<SubmissionPublic>(`/hackathons/submissions/${submissionId}/grade`, { score, feedback })
      .then((r) => r.data),
};
