import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { candidatesApi, useOverview } from "@/features/pentrix-ops/api/candidates-api";
import { pentrixKeys } from "@/features/pentrix-ops/api/pentrix-ops-api";
import { AssessmentBadge, QualificationBadge } from "@/features/pentrix-ops/components/candidate-badges";
import { DailyPaymentsWidget } from "@/features/pentrix-ops/components/daily-payments-widget";
import { UpcomingBookingsWidget } from "@/features/pentrix-ops/components/upcoming-bookings-widget";
import { PAYMENT_LABEL, agoOrDate, dayMonthIst, usePentrixPermissions } from "@/features/pentrix-ops/lib/format";
import { errorMessage } from "@/features/institutions/lib/format";

function Tile({ label, value, to, hint }: { label: string; value: number; to?: string; hint?: string }) {
  const body = (
    <CardContent className="p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-3xl font-semibold tabular-nums">{value.toLocaleString("en-IN")}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </CardContent>
  );
  return <Card className={to ? "transition-colors hover:bg-muted/40" : undefined}>{to ? <Link to={to} aria-label={`${label}: ${value}`}>{body}</Link> : body}</Card>;
}

function Bars({ rows }: { rows: { label: string; count: number }[] }) {
  const max = Math.max(...rows.map((r) => r.count), 1);
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.label}>
          <div className="mb-1 flex justify-between text-sm">
            <span>{r.label}</span>
            <span className="tabular-nums text-muted-foreground">{r.count.toLocaleString("en-IN")}</span>
          </div>
          <div className="h-2 rounded-full bg-muted" role="presentation">
            <div className="h-2 rounded-full bg-primary" style={{ width: `${(r.count / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** How the Pentrix programme is doing: who has registered, been assessed, qualified, booked and paid. */
export function OverviewPage() {
  const perms = usePentrixPermissions();
  const queryClient = useQueryClient();
  const overview = useOverview();
  const sync = useMutation({
    mutationFn: async () => {
      if (perms.canRegistrations) await candidatesApi.sync();
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: pentrixKeys.all }),
  });
  const data = overview.data;
  const link = (to: string) => (perms.canRegistrations ? to : undefined);

  return (
    <div className="space-y-6 p-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Pentrix Overview</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Registration, assessment, qualification, booking and payment across the Pentrix programme. Pentrix is the source of truth; ERPX keeps this view up to date every minute.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {data?.last_synced_at && <span className="text-xs text-muted-foreground">Last checked with Pentrix {agoOrDate(data.last_synced_at)}</span>}
          {perms.canRegistrations && (
            <Button variant="outline" disabled={sync.isPending} onClick={() => sync.mutate()}>
              <RefreshCw className={`h-4 w-4 ${sync.isPending ? "animate-spin" : ""}`} /> Refresh from Pentrix
            </Button>
          )}
        </div>
      </div>
      {sync.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(sync.error, "Could not reach Pentrix.")}</p>}
      {overview.isLoading && <Skeleton className="h-48" />}
      {overview.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(overview.error, "Could not load the overview.")}</p>}

      {data && !data.configured && (
        <p role="status" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
          The connection to Pentrix is not configured, so these numbers are not being updated.
        </p>
      )}
      {data?.last_sync_error && (
        <p role="status" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
          The last update from Pentrix did not complete ({data.last_sync_error}). It will try again within a minute.
        </p>
      )}

      {data && (
        <>
          <section aria-label="Key numbers" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Tile label="Registered candidates" value={data.totals.registered} to={link("/pentrix-ops/registrations")} hint={`${data.totals.registered_today} today · ${data.totals.registered_last_7_days} in the last 7 days`} />
            <Tile label="Assessments completed" value={data.totals.assessments_completed} to={link("/pentrix-ops/registrations?assessment=completed")} hint={`${data.totals.assessments_in_progress} in progress`} />
            <Tile label="Qualified" value={data.totals.qualified} to={link("/pentrix-ops/registrations?qualification=qualified")} />
            <Tile label="Not qualified" value={data.totals.not_qualified} to={link("/pentrix-ops/registrations?qualification=not_qualified")} hint="Took the assessment and missed the criteria" />
            <Tile label="Upcoming bookings" value={data.bookings.upcoming} to={perms.canView ? "/pentrix-ops/bookings" : undefined} />
            <Tile label="Today's bookings" value={data.bookings.today} to={perms.canView ? "/pentrix-ops/bookings" : undefined} />
            <Tile label="Paid candidates" value={data.totals.paid} to={link("/pentrix-ops/registrations?payment=paid")} />
            <Tile label="Payments pending" value={data.totals.payment_pending} to={link("/pentrix-ops/registrations?payment=pending")} />
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Candidate journey</CardTitle>
                <CardDescription>How many have reached each step.</CardDescription>
              </CardHeader>
              <CardContent>
                <Bars rows={data.funnel.map((f) => ({ label: f.label, count: f.count }))} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Payment status</CardTitle>
                <CardDescription>Candidates by where their payment stands.</CardDescription>
              </CardHeader>
              <CardContent>
                <Bars rows={(["paid", "pending", "failed", "refunded", "none"] as const).map((k) => ({ label: PAYMENT_LABEL[k], count: data.payment_status[k] }))} />
              </CardContent>
            </Card>
          </div>

          {perms.canView && <UpcomingBookingsWidget />}
          <DailyPaymentsWidget withRecent />

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle className="text-base">Recent registrations</CardTitle>
                  <CardDescription>The newest candidates.</CardDescription>
                </div>
                {perms.canRegistrations && <Link to="/pentrix-ops/registrations" className="text-sm text-primary hover:underline">View Registrations</Link>}
              </CardHeader>
              <CardContent>
                {data.recent_registrations.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Nobody has registered yet.</p>
                ) : (
                  <ul className="divide-y">
                    {data.recent_registrations.map((c) => (
                      <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                        <div>
                          {perms.canRegistrations ? (
                            <Link className="font-medium hover:underline" to={`/pentrix-ops/registrations/${c.id}`}>{c.full_name || "Candidate"}</Link>
                          ) : (
                            <span className="font-medium">{c.full_name || "Candidate"}</span>
                          )}
                          <div className="text-xs text-muted-foreground">{c.email} · {dayMonthIst(c.registered_at)}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <AssessmentBadge assessment={c.assessment} />
                          <QualificationBadge qualified={c.assessment.qualified} />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Quick actions</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {perms.canRegistrations && (
                  <>
                    <Button asChild variant="outline" className="justify-start"><Link to="/pentrix-ops/registrations">View Registrations</Link></Button>
                    <Button asChild variant="outline" className="justify-start"><Link to="/pentrix-ops/registrations?qualification=qualified">View Qualified Candidates</Link></Button>
                  </>
                )}
                {perms.canView && <Button asChild variant="outline" className="justify-start"><Link to="/pentrix-ops/bookings">Manage Bookings</Link></Button>}
                {perms.canAssessments && <Button asChild variant="outline" className="justify-start"><Link to="/pentrix-ops/assessments">Review Assessments</Link></Button>}
                {perms.canPayments && <Button asChild variant="outline" className="justify-start"><Link to="/pentrix-ops/payments">Review Payments</Link></Button>}
                {perms.canSendMarketing && <Button asChild variant="outline" className="justify-start"><Link to="/pentrix-ops/registrations?marketing=opted_in">Send Marketing Emails</Link></Button>}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
