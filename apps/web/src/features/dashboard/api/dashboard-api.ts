import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

export interface DashboardSummary {
  organization_name: string;
  subscription_plan: "trial" | "basic" | "professional" | "enterprise";
  total_users: number;
  total_branches: number;
  total_roles: number;
  organization_created_at: string;
}

export const dashboardApi = {
  getSummary: () => apiClient.get<DashboardSummary>("/dashboard/summary").then((r) => r.data),
};

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: dashboardApi.getSummary,
    retry: false,
  });
}
