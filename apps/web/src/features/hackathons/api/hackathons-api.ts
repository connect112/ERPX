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
  leaderboard_visible: boolean;
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
  leaderboard_visible?: boolean;
}

export interface TeamPublic {
  id: string;
  hackathon_id: string;
  created_by_student_id: string;
  name: string;
  created_at: string;
  member_count: number;
  member_names: string[];
  tasks_submitted: number;
  total_score: number;
}

export interface ProblemStatement {
  id: string;
  hackathon_id: string;
  title: string;
  description: string;
  order_index: number;
}

export interface ParticipantsResult {
  created: number;
  resent: number;
  already_have_login: number;
  errors: { email: string; reason: string }[];
}

/** One team's work on one task (a report and/or a registry / repository URL) with its score. */
export interface TaskSubmissionAdmin {
  id: string;
  team_id: string;
  team_name: string;
  members: string[];
  task_id: string;
  task_title: string;
  task_order: number;
  repo_url: string | null;
  report_filename: string | null;
  report_size_bytes: number | null;
  submitted_at: string;
  score: number | null;
  feedback: string | null;
}

export interface LeaderboardEntry {
  rank: number;
  team_name: string;
  score: number;
  tasks_scored: number;
  members: string[];
}

export interface LeaderboardBoard {
  hackathon_id: string;
  hackathon_title: string;
  published: boolean;
  entries: LeaderboardEntry[];
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

  addParticipants: (id: string, participants: { name: string; email: string }[], resendToExisting: boolean) =>
    apiClient
      .post<ParticipantsResult>(`/hackathons/${id}/participants`, {
        participants,
        resend_to_existing: resendToExisting,
      })
      .then((r) => r.data),

  listProblemStatements: (id: string) =>
    apiClient.get<ProblemStatement[]>(`/hackathons/${id}/problem-statements`).then((r) => r.data),
  addProblemStatement: (id: string, title: string, description: string) =>
    apiClient.post<ProblemStatement>(`/hackathons/${id}/problem-statements`, { title, description }).then((r) => r.data),
  updateProblemStatement: (id: string, statementId: string, title: string, description: string) =>
    apiClient
      .put<ProblemStatement>(`/hackathons/${id}/problem-statements/${statementId}`, { title, description })
      .then((r) => r.data),
  deleteProblemStatement: (id: string, statementId: string) =>
    apiClient.delete(`/hackathons/${id}/problem-statements/${statementId}`).then((r) => r.data),

  downloadTaskReport: async (id: string, submissionId: string, filename: string) => {
    const response = await apiClient.get(`/hackathons/${id}/task-submissions/${submissionId}/report`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  },

  listTaskSubmissions: (id: string) =>
    apiClient.get<TaskSubmissionAdmin[]>(`/hackathons/${id}/task-submissions`).then((r) => r.data),

  gradeTaskSubmission: (id: string, submissionId: string, score: number, feedback?: string) =>
    apiClient
      .post(`/hackathons/${id}/task-submissions/${submissionId}/grade`, { score, feedback: feedback || null })
      .then((r) => r.data),

  leaderboard: (id: string) =>
    apiClient.get<LeaderboardBoard>(`/hackathons/${id}/leaderboard`).then((r) => r.data),
};
