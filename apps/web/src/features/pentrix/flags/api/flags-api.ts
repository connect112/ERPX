import { apiClient } from "@/api/client";

export interface FlagPublic {
  id: string;
  challenge_id: string;
  created_at: string;
}

export interface SubmissionResultResponse {
  correct: boolean;
  already_solved: boolean;
  points_awarded: number;
}

export interface SolvePublic {
  id: string;
  challenge_id: string;
  student_id: string;
  points_awarded: number;
  solved_at: string;
}

export const flagsApi = {
  setFlag: (challengeId: string, flagValue: string) =>
    apiClient
      .put<FlagPublic>(`/pentrix/challenges/${challengeId}/flag`, { flag_value: flagValue })
      .then((r) => r.data),

  submitFlag: (challengeId: string, studentId: string, flagValue: string) =>
    apiClient
      .post<SubmissionResultResponse>(`/pentrix/challenges/${challengeId}/submit`, {
        student_id: studentId,
        flag_value: flagValue,
      })
      .then((r) => r.data),

  listSolvesForStudent: (studentId: string) =>
    apiClient.get<SolvePublic[]>(`/pentrix/students/${studentId}/solves`).then((r) => r.data),
};
