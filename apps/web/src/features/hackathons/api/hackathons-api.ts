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
  resubmission_enabled: boolean;
  max_resubmissions: number;
  leaderboard_share_enabled: boolean;
  leaderboard_slug: string | null;
  leaderboard_show_members: boolean;
  /** Whether the leaderboard draws the bar graph (off: a grid of team cards). */
  leaderboard_show_graph: boolean;
  /** Where the public live leaderboard lives (set once a link name exists, even while sharing is off). */
  leaderboard_share_url: string | null;
  /** The event's countdown: counts down to the start, then to the end. */
  timer_starts_at: string | null;
  timer_ends_at: string | null;
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
  resubmission_enabled?: boolean;
  max_resubmissions?: number;
  leaderboard_share_enabled?: boolean;
  leaderboard_slug?: string;
  leaderboard_show_members?: boolean;
  leaderboard_show_graph?: boolean;
  /** ISO moments (with timezone); null clears one. */
  timer_starts_at?: string | null;
  timer_ends_at?: string | null;
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

/** A task: what it is worth, its parts, and the rubric staff mark it against. */
export interface ProblemStatement {
  id: string;
  hackathon_id: string;
  title: string;
  description: string | null;
  order_index: number;
  marks: number;
  sub_tasks: SubTask[];
  rubric: RubricRule[];
}

/** What the task form sends. An `id` on a sub-task or rule keeps it (and any marks awarded against it) when editing. */
export interface ProblemStatementInput {
  title: string;
  marks: number;
  description: string | null;
  sub_tasks: { id?: string; title: string; points: number }[];
  rubric: { id?: string; criterion: string; points: number }[];
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
  task_marks: number;
  rubric: RubricRule[];
  repo_url: string | null;
  report_filename: string | null;
  report_size_bytes: number | null;
  submitted_at: string;
  score: number | null;
  rubric_scores: Record<string, number> | null;
  /** Scored and not changed since. False for a new or a resubmitted submission. */
  reviewed: boolean;
  /** How many times the team changed it after first submitting. */
  resubmission_count: number;
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
  max_total: number;
  show_graph: boolean;
  entries: LeaderboardEntry[];
}

/** Someone to put in a team: an existing participant, or a new person (a login is created for them). */
export type MemberRef = { student_id: string } | { name: string; email: string; phone?: string };

export interface RosterMember {
  student_id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  joined_at: string;
  /** Whether the person has ever signed in (false = still hasn't set their password). */
  has_logged_in: boolean;
  is_creator: boolean;
}

export interface RosterTeam {
  id: string;
  name: string;
  /** What teammates type to join the team. */
  join_code: string;
  created_at: string;
  tasks_submitted: number;
  total_score: number;
  members: RosterMember[];
}

/** A person with a login who isn't in any team of the hackathon yet. */
export interface TeamCandidate {
  student_id: string;
  full_name: string;
  email: string | null;
  student_code: string;
}

/** Someone invited to the hackathon (or in one of its teams). */
export interface Participant {
  student_id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  student_code: string;
  invited_at: string | null;
  has_logged_in: boolean;
  last_login_at: string | null;
  team_id: string | null;
  team_name: string | null;
  is_creator: boolean;
  /** Only accounts that exist just for hackathons can be deleted outright. */
  can_delete_account: boolean;
}

export interface ParticipantBulkResult {
  done: number;
  skipped: { student_id: string; name: string; reason: string }[];
}

export interface MemberUpdatePayload {
  full_name?: string;
  email?: string;
  phone?: string;
  send_login_link?: boolean;
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

  participants: (id: string) =>
    apiClient.get<Participant[]>(`/hackathons/${id}/participants`).then((r) => r.data),
  removeParticipants: (id: string, studentIds: string[], deleteAccount: boolean) =>
    apiClient
      .post<ParticipantBulkResult>(`/hackathons/${id}/participants/remove`, {
        student_ids: studentIds,
        delete_account: deleteAccount,
      })
      .then((r) => r.data),
  sendLoginLinks: (id: string, studentIds: string[] | null) =>
    apiClient
      .post<{ message: string }>(`/hackathons/${id}/participants/login-links`, { student_ids: studentIds })
      .then((r) => r.data),
  roster: (id: string) => apiClient.get<RosterTeam[]>(`/hackathons/${id}/roster`).then((r) => r.data),
  candidates: (id: string, q: string) =>
    apiClient.get<TeamCandidate[]>(`/hackathons/${id}/candidates`, { params: { q } }).then((r) => r.data),
  createTeam: (id: string, name: string, member: MemberRef) =>
    apiClient.post<{ message: string }>(`/hackathons/${id}/teams`, { name, member }).then((r) => r.data),
  renameTeam: (id: string, teamId: string, name: string) =>
    apiClient.patch<{ message: string }>(`/hackathons/${id}/teams/${teamId}`, { name }).then((r) => r.data),
  regenerateTeamCode: (id: string, teamId: string) =>
    apiClient.post<{ message: string }>(`/hackathons/${id}/teams/${teamId}/code`).then((r) => r.data),
  deleteTeam: (id: string, teamId: string) =>
    apiClient.delete<{ message: string }>(`/hackathons/${id}/teams/${teamId}`).then((r) => r.data),
  addMember: (id: string, teamId: string, member: MemberRef) =>
    apiClient.post<{ message: string }>(`/hackathons/${id}/teams/${teamId}/members`, member).then((r) => r.data),
  removeMember: (id: string, teamId: string, studentId: string) =>
    apiClient
      .delete<{ message: string }>(`/hackathons/${id}/teams/${teamId}/members/${studentId}`)
      .then((r) => r.data),
  moveMember: (id: string, studentId: string, teamId: string) =>
    apiClient
      .post<{ message: string }>(`/hackathons/${id}/members/${studentId}/move`, { team_id: teamId })
      .then((r) => r.data),
  updateMember: (id: string, studentId: string, payload: MemberUpdatePayload) =>
    apiClient.patch<{ message: string }>(`/hackathons/${id}/members/${studentId}`, payload).then((r) => r.data),
  sendLoginLink: (id: string, studentId: string) =>
    apiClient.post<{ message: string }>(`/hackathons/${id}/members/${studentId}/login-link`).then((r) => r.data),

  addParticipants: (id: string, participants: { name: string; email: string }[], resendToExisting: boolean) =>
    apiClient
      .post<ParticipantsResult>(`/hackathons/${id}/participants`, {
        participants,
        resend_to_existing: resendToExisting,
      })
      .then((r) => r.data),

  listProblemStatements: (id: string) =>
    apiClient.get<ProblemStatement[]>(`/hackathons/${id}/problem-statements`).then((r) => r.data),
  addProblemStatement: (id: string, input: ProblemStatementInput) =>
    apiClient.post<ProblemStatement>(`/hackathons/${id}/problem-statements`, input).then((r) => r.data),
  updateProblemStatement: (id: string, statementId: string, input: ProblemStatementInput) =>
    apiClient
      .put<ProblemStatement>(`/hackathons/${id}/problem-statements/${statementId}`, input)
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

  /** Marks for one submission: a mark per rubric rule, or one score when the task has no rubric. */
  gradeTaskSubmission: (
    id: string,
    submissionId: string,
    marks: { score?: number; rubricScores?: Record<string, number> },
    feedback?: string
  ) =>
    apiClient
      .post(`/hackathons/${id}/task-submissions/${submissionId}/grade`, {
        score: marks.score ?? null,
        rubric_scores: marks.rubricScores ?? null,
        feedback: feedback || null,
      })
      .then((r) => r.data),

  /** Delete a team's submission (and its marks); the team can then submit that task again. */
  deleteTaskSubmission: (id: string, submissionId: string) =>
    apiClient.delete(`/hackathons/${id}/task-submissions/${submissionId}`).then(() => undefined),

  /** The submitted report as a Blob (for the in-page preview). */
  fetchTaskReport: (id: string, submissionId: string) =>
    apiClient
      .get<Blob>(`/hackathons/${id}/task-submissions/${submissionId}/report`, { responseType: "blob" })
      .then((r) => r.data),

  leaderboard: (id: string) =>
    apiClient.get<LeaderboardBoard>(`/hackathons/${id}/leaderboard`).then((r) => r.data),
};
