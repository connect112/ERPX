import { apiClient } from "@/api/client";

export type HealthStatus = "healthy" | "unhealthy" | "degraded";

export interface HealthCheckResult {
  component: string;
  status: HealthStatus;
  latency_ms: number | null;
  detail: string | null;
  message: string | null;
}

export interface SystemHealthResponse {
  overall_status: HealthStatus;
  checks: HealthCheckResult[];
}

export interface PlatformStatsResponse {
  organization_count: number;
  user_count: number;
  student_count: number;
  audit_events_last_24h: number;
}

export const monitoringApi = {
  health: () => apiClient.get<SystemHealthResponse>("/monitoring/health").then((r) => r.data),
  stats: () => apiClient.get<PlatformStatsResponse>("/monitoring/stats").then((r) => r.data),
};
