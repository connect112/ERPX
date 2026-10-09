import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { Report, ReportPost } from "@/features/social-media/api/social-media-api";
import { useGenerateReport, useReports } from "@/features/social-media/api/social-media-hooks";
import { ExperimentsPanel } from "@/features/social-media/components/experiments-panel";
import { GroupTable } from "@/features/social-media/components/group-table";
import { errorMessage, formatInZone } from "@/features/social-media/lib/format";
import { KIND_LABEL, NOT_AVAILABLE, formatChange, formatDay, formatNumber, formatRate, signed } from "@/features/social-media/lib/numbers";

const ZONE = "Asia/Kolkata";

function title(r: Pick<Report, "kind" | "period_start" | "period_end">): string {
  return `${r.kind === "weekly" ? "Week" : "Month"}: ${formatDay(r.period_start)} to ${formatDay(r.period_end)}`;
}

function Findings({ heading, items, tone }: { heading: string; items: string[]; tone: string }) {
  return (
    <div className={`rounded-md border p-3 ${tone}`}>
      <p className="mb-1 text-sm font-medium">{heading}</p>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground">Nothing to report.</p>
      ) : (
        <ul className="list-disc space-y-1 pl-4 text-sm">
          {items.map((i) => (
            <li key={i}>{i}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PostLine({ p }: { p: ReportPost }) {
  return (
    <li className="text-sm">
      <span className="font-medium">{p.title}</span> ({p.kind}): reached {formatNumber(p.reach)}, views {formatNumber(p.views)}, saves {formatNumber(p.saves)}, shares {formatNumber(p.shares)}, engagement by reach {formatRate(p.er_reach)}
    </li>
  );
}

function ReportView({ report }: { report: Report }) {
  const d = report.data;
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">{title(report)}</h3>
        <p className="text-xs text-muted-foreground">
          Made {formatInZone(report.generated_at, ZONE)} {report.automatic ? "automatically" : `by ${report.generated_by ?? "a person"}`}. Worked out from the figures ERPX holds, using fixed rules (no AI wrote it).
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <Findings heading="What worked" items={d.findings.worked} tone="border-emerald-300 bg-emerald-50/50" />
        <Findings heading="What didn't" items={d.findings.didnt} tone="border-amber-300 bg-amber-50/50" />
        <Findings heading="What to test next" items={d.findings.test_next} tone="" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Profile figures</CardTitle>
          <CardDescription>Each is Instagram&apos;s own (observed). Days Instagram gave no figure for are not counted as zero.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">Figure</th>
                <th className="py-2 pr-3 font-medium">Value</th>
                <th className="py-2 pr-3 font-medium">Days with a figure</th>
                <th className="py-2 pr-3 font-medium">Compared with the period before</th>
              </tr>
            </thead>
            <tbody>
              {d.account.cards.map((c) => (
                <tr key={c.key} className="border-t">
                  <td className="py-2 pr-3">
                    {c.label} <Badge variant="outline">{KIND_LABEL[c.kind]}</Badge>
                  </td>
                  <td className="py-2 pr-3">
                    {formatNumber(c.value)}
                    {c.value !== null && <span className="text-xs text-muted-foreground"> {c.value_kind === "total" ? "total" : "per day"}</span>}
                  </td>
                  <td className="py-2 pr-3">
                    {c.days_with_data} of {c.days_in_period}
                  </td>
                  <td className="py-2 pr-3">{formatChange(c.change_vs_previous) ?? NOT_AVAILABLE}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted-foreground">
            Followers: {d.account.followers.change !== null ? `${signed(d.account.followers.change)} between the first and last snapshot in the period (calculated, a net figure)` : "needs snapshots on at least two days in this period"}.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Posts</CardTitle>
          <CardDescription>
            {d.posts.on_instagram} post(s) on Instagram this period, {d.posts.insights_read} with readable figures. {d.posts.er_reach_posts > 0 ? `Engagement by reach across them: ${formatRate(d.posts.er_reach_pooled)} (${d.posts.er_reach_posts} posts). ` : ""}
            {d.posts.er_reach_note}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {d.posts.top.length > 0 && (
            <div>
              <p className="text-sm font-medium">Reached the most accounts</p>
              <ul className="list-disc space-y-1 pl-4">
                {d.posts.top.map((p) => (
                  <PostLine key={p.external_id} p={p} />
                ))}
              </ul>
            </div>
          )}
          {d.posts.lowest.length > 0 && (
            <div>
              <p className="text-sm font-medium">Reached the fewest</p>
              <ul className="list-disc space-y-1 pl-4">
                {d.posts.lowest.map((p) => (
                  <PostLine key={p.external_id} p={p} />
                ))}
              </ul>
            </div>
          )}
          <div>
            <p className="mb-1 text-sm font-medium">By format</p>
            <GroupTable rows={d.posts.by_format} />
          </div>
          <div>
            <p className="mb-1 text-sm font-medium">By topic</p>
            <GroupTable rows={d.posts.by_pillar} />
          </div>
          <p className="text-xs text-muted-foreground">
            Consistency: {d.consistency.posts} post(s) on {d.consistency.days_with_a_post} of {d.consistency.days_in_period} days
            {d.consistency.longest_gap_days !== null ? `, longest stretch without a post ${d.consistency.longest_gap_days} day(s)` : ""} (calculated).
          </p>
        </CardContent>
      </Card>

      <div className="rounded-md border p-3">
        <p className="mb-1 text-sm font-medium">Please remember</p>
        <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
          {d.caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/** Weekly and monthly reports (one is made automatically each time a week or month ends) and the experiments log. */
export function ReportsTab() {
  const reports = useReports();
  const generate = useGenerateReport();
  const me = useMyRoles();
  const [openId, setOpenId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const canManage = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.manage");
  const items = reports.data ?? [];
  const shown = items.find((r) => r.id === openId) ?? items[0];

  function make(kind: "weekly" | "monthly") {
    setNotice(null);
    generate.mutate(
      { kind },
      {
        onSuccess: (r) => {
          setOpenId(r.id);
          setNotice({ ok: true, text: `${title(r)} is ready.` });
        },
        onError: (e) => setNotice({ ok: false, text: errorMessage(e, "Couldn't make the report.") }),
      },
    );
  }

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            What worked, what didn&apos;t and what to test next, from Instagram&apos;s figures. A report is made automatically when a week or month ends. It describes what happened; it doesn&apos;t predict growth or prove what caused a change.
          </p>
          {canManage && (
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={generate.isPending} onClick={() => make("weekly")}>
                {generate.isPending ? "Working…" : "Make last week's report"}
              </Button>
              <Button size="sm" variant="outline" disabled={generate.isPending} onClick={() => make("monthly")}>
                Make last month&apos;s report
              </Button>
            </div>
          )}
        </div>
        {notice && (
          <p role={notice.ok ? "status" : "alert"} className={notice.ok ? "text-sm text-emerald-800" : "text-sm text-destructive"}>
            {notice.text}
          </p>
        )}
        {reports.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : items.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">No reports yet. The first one appears when a week or month ends, or make one above.</CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
            <div className="flex max-h-72 gap-1 overflow-auto lg:max-h-none lg:flex-col" role="group" aria-label="Reports">
              {items.map((r) => (
                <Button key={r.id} size="sm" className="shrink-0 justify-start" variant={shown?.id === r.id ? "default" : "outline"} onClick={() => setOpenId(r.id)}>
                  {title(r)}
                </Button>
              ))}
            </div>
            {shown && <ReportView report={shown} />}
          </div>
        )}
      </div>
      <ExperimentsPanel canManage={canManage} />
    </div>
  );
}
