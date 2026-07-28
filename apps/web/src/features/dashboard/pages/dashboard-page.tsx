import { Building2, Shield, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDashboardSummary } from "@/features/dashboard/api/dashboard-api";
import { useAuthStore } from "@/store/auth-store";

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  icon: typeof Users;
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-6">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold">{value}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const { data, isLoading, isError, error } = useDashboardSummary();

  const noOrgError =
    isError &&
    (error as { response?: { data?: { error?: { code?: string } } } })?.response?.data?.error
      ?.code === "validation_error";

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Welcome back{user ? `, ${user.fullName.split(" ")[0]}` : ""}
        </h1>
        <p className="mt-1 text-muted-foreground">
          {data ? data.organization_name : "Here's what's happening across your organization."}
        </p>
      </div>

      {isLoading && <p className="text-muted-foreground">Loading dashboard...</p>}

      {noOrgError && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">No organization linked yet</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Your account isn't associated with an organization yet. Ask an administrator to link
            your profile to get full access to your dashboard.
          </CardContent>
        </Card>
      )}

      {data && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard label="Team members" value={data.total_users} icon={Users} />
          <StatCard label="Branches" value={data.total_branches} icon={Building2} />
          <StatCard label="Roles configured" value={data.total_roles} icon={Shield} />
        </div>
      )}

      {data && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Subscription</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            You're on the{" "}
            <span className="font-medium capitalize text-foreground">
              {data.subscription_plan}
            </span>{" "}
            plan.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
