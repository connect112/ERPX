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
  leaderboard_visible: boolean;
  created_at: string;
}

export interface TeamPublic {
  id: string;
  hackathon_id: string;
  created_by_student_id: string;
  name: string;
  created_at: string;
  member_count: number;
  problem_statement_id: string | null;
  problem_statement_title: string | null;
}

export interface TeamMemberPublic {
  id: string;
  team_id: string;
  student_id: string;
  student_name: string;
  joined_at: string;
}

export interface ReportInfo {
  filename: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface TeamWithMembersPublic {
  team: TeamPublic;
  members: TeamMemberPublic[];
  report: ReportInfo | null;
}

export interface ProblemStatement {
  id: string;
  hackathon_id: string;
  title: string;
  description: string;
  order_index: number;
}

export interface LeaderboardEntry {
  rank: number;
  team_name: string;
  score: number;
  project_title: string;
  members: string[];
}

export interface LeaderboardBoard {
  hackathon_id: string;
  hackathon_title: string;
  published: boolean;
  entries: LeaderboardEntry[];
}

export interface Award {
  hackathon_id: string;
  hackathon_title: string;
  team_name: string;
  code: "participant" | "submitted" | "report" | "winner" | "runner_up" | "third_place";
  label: string;
  detail: string;
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

  problemStatements: (hackathonId: string) =>
    apiClient.get<ProblemStatement[]>(`/hackathons/${hackathonId}/problem-statements/me`).then((r) => r.data),

  chooseProblem: (hackathonId: string, problemStatementId: string | null) =>
    apiClient
      .put<TeamPublic>(`/hackathons/${hackathonId}/teams/me/problem-statement`, {
        problem_statement_id: problemStatementId,
      })
      .then((r) => r.data),

  uploadReport: (hackathonId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    // apiClient defaults to a JSON Content-Type, under which axios would turn
    // the FormData into JSON; naming multipart lets the browser add the boundary.
    return apiClient
      .put<ReportInfo>(`/hackathons/${hackathonId}/teams/me/report`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  downloadReport: async (hackathonId: string, filename: string) => {
    const response = await apiClient.get(`/hackathons/${hackathonId}/teams/me/report/download`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  },

  leaderboards: () => apiClient.get<LeaderboardBoard[]>("/hackathons/leaderboard/me").then((r) => r.data),

  achievements: () => apiClient.get<Award[]>("/hackathons/achievements/me").then((r) => r.data),

  submitProject: (
    hackathonId: string,
    teamId: string,
    payload: { title: string; description?: string; repo_url?: string; demo_url?: string }
  ) =>
    apiClient
      .post<SubmissionPublic>(`/hackathons/${hackathonId}/teams/${teamId}/submissions/me`, payload)
      .then((r) => r.data),
};
