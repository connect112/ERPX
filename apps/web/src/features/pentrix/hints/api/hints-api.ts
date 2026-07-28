import { apiClient } from "@/api/client";

export interface HintPublic {
  id: string;
  challenge_id: string;
  hint_text: string;
  point_cost: number;
  order_index: number;
}

export interface HintLocked {
  id: string;
  challenge_id: string;
  point_cost: number;
  order_index: number;
  unlocked: boolean;
}

export interface HintUnlockResponse {
  hint_id: string;
  hint_text: string;
  point_cost: number;
}

export interface HintCreatePayload {
  hint_text: string;
  point_cost?: number;
  order_index: number;
}

export const hintsApi = {
  create: (challengeId: string, payload: HintCreatePayload) =>
    apiClient
      .post<HintPublic>(`/pentrix/challenges/${challengeId}/hints`, payload)
      .then((r) => r.data),

  listForStudent: (challengeId: string, studentId: string) =>
    apiClient
      .get<HintLocked[]>(`/pentrix/challenges/${challengeId}/hints`, { params: { student_id: studentId } })
      .then((r) => r.data),

  unlock: (hintId: string, studentId: string) =>
    apiClient
      .post<HintUnlockResponse>(`/pentrix/hints/${hintId}/unlock`, { student_id: studentId })
      .then((r) => r.data),
};
