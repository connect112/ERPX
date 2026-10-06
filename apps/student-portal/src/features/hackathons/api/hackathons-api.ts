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

export interface ReportInfo {
  filename: string;
  size_bytes: number;
  uploaded_at: string;
}

/** The team's work on one task: a report file and/or a repository / registry URL, plus the staff score. */
export interface TaskSubmission {
  id: string;
  repo_url: string | null;
  report: ReportInfo | null;
  submitted_at: string;
  score: number | null;
  feedback: string | null;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  order_index: number;
  submission: TaskSubmission | null;
}

export interface TasksResponse {
  team_id: string | null;
  can_submit: boolean;
  tasks: Task[];
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

export interface Award {
  hackathon_id: string;
  hackathon_title: string;
  team_name: string;
  code: "participant" | "submitted" | "winner" | "runner_up" | "third_place";
  label: string;
  detail: string;
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

  tasks: (hackathonId: string) =>
    apiClient.get<TasksResponse>(`/hackathons/${hackathonId}/tasks/me`).then((r) => r.data),

  /**
   * Submit (or update) the team's work on one task. `repoUrl` is always sent
   * (an empty string clears it); `file` is only sent when a new report was
   * chosen, otherwise the saved report is kept.
   */
  submitTask: (hackathonId: string, taskId: string, payload: { repoUrl: string; file: File | null }) => {
    const form = new FormData();
    form.append("repo_url", payload.repoUrl);
    if (payload.file) form.append("file", payload.file);
    // apiClient defaults to a JSON Content-Type, under which axios would turn
    // the FormData into JSON; naming multipart lets the browser add the boundary.
    return apiClient
      .put<TaskSubmission>(`/hackathons/${hackathonId}/tasks/${taskId}/submission/me`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  downloadTaskReport: async (hackathonId: string, taskId: string, filename: string) => {
    const response = await apiClient.get(`/hackathons/${hackathonId}/tasks/${taskId}/submission/me/report`, {
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
};
