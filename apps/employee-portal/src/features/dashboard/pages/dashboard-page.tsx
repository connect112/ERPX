import { format, parseISO } from "date-fns";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyEmployeeProfile } from "@/features/dashboard/api/employee-hooks";

const statusVariant: Record<string, "success" | "secondary" | "outline" | "destructive"> = {
  active: "success",
  on_leave: "secondary",
  resigned: "outline",
  terminated: "destructive",
  retired: "outline",
};

function statusLabel(status: string): string {
  return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function DashboardPage() {
  const { data: employee, isLoading } = useMyEmployeeProfile();

  return (
    <div className="space-y-6 p-6">
      <div>
        {isLoading ? (
          <Skeleton className="h-8 w-64" />
        ) : (
          <h1 className="text-2xl font-semibold">Welcome back, {employee?.full_name}</h1>
        )}
        <p className="text-sm text-muted-foreground">Your profile and employment details.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Employee code</CardDescription>
            <CardTitle className="text-lg">{isLoading ? "…" : employee?.employee_code}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Status</CardDescription>
            <CardTitle className="text-lg">
              {isLoading ? (
                "…"
              ) : (
                <Badge variant={statusVariant[employee?.employment_status ?? ""] ?? "outline"}>
                  {statusLabel(employee?.employment_status ?? "")}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Joined</CardDescription>
            <CardTitle className="text-lg">
              {isLoading || !employee?.date_of_joining
                ? "…"
                : format(parseISO(employee.date_of_joining), "PP")}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">My details</CardTitle>
          <CardDescription>Contact HR to correct anything here.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
            </div>
          ) : (
            <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
              <div>
                <dt className="text-xs text-muted-foreground">Email</dt>
                <dd className="text-sm">{employee?.email ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Phone</dt>
                <dd className="text-sm">{employee?.phone ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Employment type</dt>
                <dd className="text-sm">
                  {employee ? statusLabel(employee.employment_type) : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Emergency contact</dt>
                <dd className="text-sm">
                  {employee?.emergency_contact_name
                    ? `${employee.emergency_contact_name} (${employee.emergency_contact_phone ?? "—"})`
                    : "—"}
                </dd>
              </div>
            </dl>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
