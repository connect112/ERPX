import { apiClient } from "@/api/client";

export interface LeaderboardEntry {
  student_id: string;
  student_name: string;
  student_code: string;
  challenges_solved: number;
  points_earned: number;
  points_spent_on_hints: number;
  net_score: number;
}

export const leaderboardApi = {
  get: (limit = 50) =>
    apiClient
      .get<LeaderboardEntry[]>("/pentrix/leaderboard", { params: { limit } })
      .then((r) => r.data),
};
