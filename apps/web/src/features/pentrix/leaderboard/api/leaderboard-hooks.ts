import { useQuery } from "@tanstack/react-query";

import { leaderboardApi } from "@/features/pentrix/leaderboard/api/leaderboard-api";

export function useLeaderboard(limit = 50) {
  return useQuery({
    queryKey: ["pentrix", "leaderboard", limit],
    queryFn: () => leaderboardApi.get(limit),
  });
}
