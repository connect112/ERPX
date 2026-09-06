import { useQuery } from "@tanstack/react-query";

import { leaderboardApi } from "@/features/leaderboard/api/leaderboard-api";

export function useLeaderboard() {
  return useQuery({
    queryKey: ["pentrix", "leaderboard"],
    queryFn: () => leaderboardApi.list(),
  });
}
