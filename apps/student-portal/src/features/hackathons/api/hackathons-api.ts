import { apiClient } from "@/api/client";

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
  status: "draft" | "registration_open" | "ongoing" | "completed" | "cancelled";
  created_at: string;
}

export interface TeamPublic {
  id: string;
  hackathon_id: string;
  created_by_student_id: string;
  name: string;
  created_at: string;
}

export interface TeamMemberPublic {
  id: string;
  team_id: string;
  student_id: string;
  student_name: string;
  joined_at: string;
}

export interface TeamWithMembersPublic {
  team: TeamPublic;
  members: TeamMemberPublic[];
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
  browse: () => apiClient.get<HackathonPublic[]>("/hackathons/me").then((r) => r.data),

  myTeam: (hackathonId: string) =>
    apiClient
      .get<TeamWithMembersPublic | null>(`/hackathons/${hackathonId}/teams/me`)
      .then((r) => r.data),

  createTeam: (hackathonId: string, name: string) =>
    apiClient
      .post<TeamPublic>(`/hackathons/${hackathonId}/teams/me`, { name })
      .then((r) => r.data),

  browseTeams: (hackathonId: string) =>
    apiClient.get<TeamPublic[]>(`/hackathons/${hackathonId}/teams/browse`).then((r) => r.data),

  joinTeam: (hackathonId: string, teamId: string) =>
    apiClient
      .post<TeamMemberPublic>(`/hackathons/${hackathonId}/teams/${teamId}/join/me`)
      .then((r) => r.data),

  getSubmission: (hackathonId: string, teamId: string) =>
    apiClient
      .get<SubmissionPublic | null>(`/hackathons/${hackathonId}/teams/${teamId}/submissions/me`)
      .then((r) => r.data),

  submitProject: (
    hackathonId: string,
    teamId: string,
    payload: { title: string; description?: string; repo_url?: string; demo_url?: string }
  ) =>
    apiClient
      .post<SubmissionPublic>(`/hackathons/${hackathonId}/teams/${teamId}/submissions/me`, payload)
      .then((r) => r.data),
};
