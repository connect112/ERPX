import { Database, HardDrive, Server, Users, Building2, GraduationCap, History } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { HealthStatusBadge } from "@/features/monitoring/components/health-status-badge";
import { usePlatformStats, useSystemHealth } from "@/features/monitoring/api/monitoring-hooks";
import type { HealthCheckResult } from "@/features/monitoring/api/monitoring-api";

const componentIcons: Record<string, typeof Database> = {
  database: Database,
  storage: HardDrive,
  redis: Server,
};

const componentLabels: Record<string, string> = {
  database: "Database",
  storage: "Object Storage",
  redis: "Redis / Queue",
};

function HealthCheckCard({ check }: { check: HealthCheckResult }) {
  const Icon = componentIcons[check.component] ?? Server;
  return (
    <Card>
      <CardContent className="space-y-2 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">{componentLabels[check.component] ?? check.component}</span>
          </div>
          <HealthStatusBadge status={check.status} />
        </div>
        {check.latency_ms !== null && (
          <p className="text-sm text-muted-foreground">Latency: {check.latency_ms.toFixed(1)} ms</p>
        )}
        {check.detail && <p className="text-sm text-muted-foreground">{check.detail}</p>}
        {check.message && (
          <p className="text-sm text-destructive" title={check.message}>
            {check.message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Database;
  label: string;
  value: number | undefined;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-6">
        <div className="rounded-full bg-muted p-3">
          <Icon className="h-5 w-5 text-muted-foreground" />
        </div>
        <div>
          <p className="text-2xl font-semibold tracking-tight">{value ?? "—"}</p>
          <p className="text-sm text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export function MonitoringPage() {
  const { data: health, isLoading: healthLoading, isError: healthError } = useSystemHealth();
  const { data: stats, isLoading: statsLoading, isError: statsError } = usePlatformStats();

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">System Health</h1>
          <p className="mt-1 text-muted-foreground">
            Live infrastructure checks and platform-wide statistics. Refreshes every 30 seconds.
            Administrator-only.
          </p>
        </div>
        {health && <HealthStatusBadge status={health.overall_status} />}
      </div>

      {healthLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      )}

      {healthError && (
        <p className="text-sm text-destructive">Failed to load system health. Please try again.</p>
      )}

      {health && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {health.checks.map((check) => (
            <HealthCheckCard key={check.component} check={check} />
          ))}
        </div>
      )}

      <div>
        <h2 className="mb-3 text-lg font-semibold tracking-tight">Platform Stats</h2>
        {statsLoading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        )}

        {statsError && (
          <p className="text-sm text-destructive">Failed to load platform stats. Please try again.</p>
        )}

        {stats && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={Building2} label="Organizations" value={stats.organization_count} />
            <StatCard icon={Users} label="Users" value={stats.user_count} />
            <StatCard icon={GraduationCap} label="Students" value={stats.student_count} />
            <StatCard icon={History} label="Audit events (24h)" value={stats.audit_events_last_24h} />
          </div>
        )}
      </div>
    </div>
  );
}
