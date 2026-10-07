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
  /** The event's countdown (set by the organiser). */
  timer_starts_at: string | null;
  timer_ends_at: string | null;
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

/** A team as its own members see it: with the code teammates type to join. */
export interface TeamOwnPublic extends TeamPublic {
  join_code: string;
}

export interface TeamMemberPublic {
  id: string;
  team_id: string;
  student_id: string;
  student_name: string;
  joined_at: string;
}

export interface TeamWithMembersPublic {
  team: TeamOwnPublic;
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
  /** Marks awarded per rubric rule (by rule id); null until the submission has been scored. */
  rubric_scores: Record<string, number> | null;
  feedback: string | null;
  /** How many times the team has changed this submission after first making it. */
  resubmission_count: number;
  /** False while the latest version hasn't been scored yet (any score shown is for an earlier version). */
  reviewed: boolean;
}

export interface SubTask {
  id: string;
  title: string;
  points: number;
}

export interface RubricRule {
  id: string;
  criterion: string;
  points: number;
}

export interface Task {
  id: string;
  title: string;
  description: string | null;
  order_index: number;
  marks: number;
  sub_tasks: SubTask[];
  rubric: RubricRule[];
  submission: TaskSubmission | null;
  /** This team's place among the teams scored on this task (only while the leaderboard is shown). */
  task_rank: number | null;
  task_teams_scored: number;
  /** Whether the team may change this submission now, and how many changes remain. */
  can_resubmit: boolean;
  resubmissions_left: number;
}

export interface TasksResponse {
  team_id: string | null;
  can_submit: boolean;
  max_total: number;
  leaderboard_visible: boolean;
  resubmission_enabled: boolean;
  max_resubmissions: number;
  team_rank: number | null;
  team_total: number;
  teams_ranked: number;
  tasks: Task[];
}

export interface LeaderboardEntry {
  rank: number;
  team_name: string;
  score: number;
  tasks_scored: number;
  members: string[];
}

/** One row of the public live leaderboard. */
export interface PublicLeaderboardEntry {
  rank: number;
  team_name: string;
  score: number;
  tasks_scored: number;
  /** Empty unless the organiser chose to show member names. */
  members: string[];
}

export interface PublicLeaderboard {
  title: string;
  theme: string | null;
  status: string;
  max_total: number;
  show_members: boolean;
  updated_at: string;
  timer_starts_at: string | null;
  timer_ends_at: string | null;
  /** The server's clock when this was sent, to correct a screen with the wrong time. */
  server_time: string;
  entries: PublicLeaderboardEntry[];
}

export interface LeaderboardBoard {
  hackathon_id: string;
  hackathon_title: string;
  published: boolean;
  /** Total marks available across all tasks (the full scale of the bar chart). */
  max_total: number;
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
  /** The shared live leaderboard (open to anyone with the link). */
  publicLeaderboard: (slug: string) =>
    apiClient.get<PublicLeaderboard>(`/hackathons/public/leaderboard/${encodeURIComponent(slug)}`).then((r) => r.data),

  browse: () => apiClient.get<HackathonPublic[]>("/hackathons/me").then((r) => r.data),

  myTeam: (hackathonId: string) =>
    apiClient
      .get<TeamWithMembersPublic | null>(`/hackathons/${hackathonId}/teams/me`)
      .then((r) => r.data),

  createTeam: (hackathonId: string, name: string) =>
    apiClient
      .post<TeamPublic>(`/hackathons/${hackathonId}/teams/me`, { name })
      .then((r) => r.data),

  /** Join a team by typing the code its members (or the organisers) can see. */
  joinTeamWithCode: (hackathonId: string, code: string) =>
    apiClient
      .post<TeamMemberPublic>(`/hackathons/${hackathonId}/teams/join/me`, { code })
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
