import { useQuery } from "@tanstack/react-query";

import { monitoringApi } from "@/features/monitoring/api/monitoring-api";

const monitoringKeys = {
  health: ["monitoring", "health"] as const,
  stats: ["monitoring", "stats"] as const,
};

export function useSystemHealth() {
  return useQuery({
    queryKey: monitoringKeys.health,
    queryFn: monitoringApi.health,
    refetchInterval: 30_000,
  });
}

export function usePlatformStats() {
  return useQuery({
    queryKey: monitoringKeys.stats,
    queryFn: monitoringApi.stats,
    refetchInterval: 30_000,
  });
}
