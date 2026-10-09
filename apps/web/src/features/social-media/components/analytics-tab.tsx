import { ExternalLink, RefreshCw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import type { MetricCard, PostInsight } from "@/features/social-media/api/social-media-api";
import { useAnalyticsOverview, useAnalyticsPosts, useAnalyticsStatus, useMetricDefinitions, useSyncAnalytics } from "@/features/social-media/api/social-media-hooks";
import { DayBars } from "@/features/social-media/components/day-bars";
import { GroupTable } from "@/features/social-media/components/group-table";
import { HashtagPanel } from "@/features/social-media/components/hashtag-panel";
import { errorMessage, formatInZone } from "@/features/social-media/lib/format";
import { GROUP_LABEL, KIND_LABEL, NOT_AVAILABLE, formatChange, formatDay, formatNumber, formatRate, signed } from "@/features/social-media/lib/numbers";

const PERIODS = [7, 14, 28] as const;
const ZONE = "Asia/Kolkata";
const STAGE_LABEL: Record<string, string> = { profile: "Profile counts", media: "Post list", account: "Daily figures", posts: "Post figures" };

function About({ card }: { card: Pick<MetricCard, "definition" | "source" | "period" | "limitation" | "kind" | "last_synced_at"> }) {
  return (
    <details className="text-xs text-muted-foreground">
      <summary className="cursor-pointer select-none">About this number</summary>
      <dl className="mt-1 space-y-1">
        <div>
          <dt className="inline font-medium">What it is: </dt>
          <dd className="inline">{card.definition}</dd>
        </div>
        <div>
          <dt className="inline font-medium">Source: </dt>
          <dd className="inline">{card.source}</dd>
        </div>
        <div>
          <dt className="inline font-medium">Period: </dt>
          <dd className="inline">{card.period}</dd>
        </div>
        {card.limitation && (
          <div>
            <dt className="inline font-medium">Limits: </dt>
            <dd className="inline">{card.limitation}</dd>
          </div>
        )}
        <div>
          <dt className="inline font-medium">Last read: </dt>
          <dd className="inline">{card.last_synced_at ? formatInZone(card.last_synced_at, ZONE) : NOT_AVAILABLE}</dd>
        </div>
      </dl>
    </details>
  );
}

function Status({ canManage }: { canManage: boolean }) {
  const status = useAnalyticsStatus();
  const sync = useSyncAnalytics();
  const [notice, setNotice] = useState<string | null>(null);
  const data = status.data;
  const failures = Object.entries(data?.stages ?? {}).filter(([, s]) => s.ok === false && s.error);

  function read() {
    setNotice(null);
    sync.mutate(undefined, {
      onSuccess: (r) => setNotice(r.skipped ? (r.message ?? "Read a moment ago.") : "Read the latest figures from Instagram."),
      onError: (e) => setNotice(errorMessage(e, "Couldn't read from Instagram.")),
    });
  }

  if (status.isLoading) return <Skeleton className="h-12 w-full" />;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {!data?.connected
            ? "Instagram isn't connected. Connect it in Settings & Integrations to see figures."
            : !data.can_read
              ? "Instagram hasn't allowed reading insights yet (see Settings & Integrations, Check what it can do)."
              : data.last_sync_at
                ? `Last read from Instagram ${formatInZone(data.last_sync_at, ZONE)}. It is read once a day.`
                : "Not read from Instagram yet. It is read once a day, or press Read now."}
        </p>
        {canManage && (
          <Button size="sm" variant="outline" onClick={read} disabled={sync.isPending || !data?.connected}>
            <RefreshCw className={`mr-1 h-3.5 w-3.5 ${sync.isPending ? "animate-spin" : ""}`} />
            {sync.isPending ? "Reading…" : "Read now"}
          </Button>
        )}
      </div>
      {notice && (
        <p role="status" className="text-xs text-muted-foreground">
          {notice}
        </p>
      )}
      {failures.map(([name, stage]) => (
        <p key={name} role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-xs text-destructive">
          {STAGE_LABEL[name] ?? name}: {stage.error}
        </p>
      ))}
      {data?.unsupported_account_metrics && data.unsupported_account_metrics.length > 0 && (
        <p className="text-xs text-muted-foreground">Instagram refuses these figures for this account, so they are left out: {data.unsupported_account_metrics.join(", ")}.</p>
      )}
      {data?.notes.map((n) => (
        <p key={n} className="text-xs text-muted-foreground">
          {n}
        </p>
      ))}
    </div>
  );
}

function Cards({ days }: { days: number }) {
  const overview = useAnalyticsOverview(days);
  const [selected, setSelected] = useState("views");
  const data = overview.data;
  if (overview.isLoading) return <Skeleton className="h-40 w-full" />;
  if (overview.isError || !data) return <p className="text-sm text-destructive">Couldn&apos;t load the figures.</p>;
  const chosen = data.cards.find((c) => c.key === selected) ?? data.cards[0];
  const change = data.follower_change;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {(["followers_count", "follows_count", "media_count"] as const).map((key) => {
          const snap = data.snapshots[key];
          return (
            <Card key={key}>
              <CardContent className="space-y-1 p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm text-muted-foreground">{snap.label}</p>
                  <Badge variant="outline">{KIND_LABEL[snap.kind]}</Badge>
                </div>
                <p className="text-2xl font-semibold">{formatNumber(snap.latest)}</p>
                <p className="text-xs text-muted-foreground">{snap.latest_day ? `As read on ${formatDay(snap.latest_day)}` : "Not read yet"}</p>
                {key === "followers_count" && (
                  <p className="text-xs">
                    {change.value !== null ? (
                      <>
                        <span className="font-medium">{signed(change.value)}</span> between {formatDay(change.from_day as string)} and {formatDay(change.to_day as string)} <Badge variant="secondary">Calculated</Badge>
                      </>
                    ) : (
                      <span className="text-muted-foreground">{change.note}</span>
                    )}
                  </p>
                )}
                <About card={{ definition: key === "followers_count" ? "How many accounts follow the profile when it was read." : snap.label, source: snap.source, period: "snapshot when ERPX read it", limitation: snap.limitation, kind: snap.kind, last_synced_at: snap.last_synced_at }} />
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data.cards.map((c) => {
          const delta = formatChange(c.change_vs_previous);
          return (
            <Card key={c.key} className={c.key === chosen.key ? "ring-2 ring-primary" : ""}>
              <CardContent className="space-y-1 p-4">
                <div className="flex items-center justify-between gap-2">
                  <button type="button" className="text-left text-sm font-medium hover:underline" onClick={() => setSelected(c.key)} aria-pressed={c.key === chosen.key}>
                    {c.label}
                  </button>
                  <Badge variant="outline">{KIND_LABEL[c.kind]}</Badge>
                </div>
                <p className="text-2xl font-semibold">{formatNumber(c.value)}</p>
                <p className="text-xs text-muted-foreground">
                  {c.value === null ? "Instagram gave no figure for these days" : c.value_kind === "total" ? `Total over ${c.days_in_period} days` : "Average per day"} · {c.days_with_data} of {c.days_in_period} days have a figure
                </p>
                {delta && c.value !== null && <p className="text-xs">{delta} (compared as daily averages with the previous {c.days_in_period} days)</p>}
                <About card={c} />
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{chosen.label}, day by day</CardTitle>
          <CardDescription>
            {formatDay(data.period.start)} to {formatDay(data.period.end)}. A dashed mark is a day Instagram gave no figure for; it does not mean zero. Choose another figure above to change this chart.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DayBars series={chosen.series} label={chosen.label} />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-1 p-4 text-sm">
          <div className="flex items-center justify-between gap-2">
            <p className="font-medium">Publishing consistency</p>
            <Badge variant="secondary">Calculated</Badge>
          </div>
          <p>
            {data.consistency.posts} post(s) on {data.consistency.days_with_a_post} of {data.consistency.days_in_period} days
            {data.consistency.longest_gap_days !== null ? `, longest stretch without a post: ${data.consistency.longest_gap_days} day(s)` : ""}.
          </p>
          <p className="text-xs text-muted-foreground">
            {data.consistency.source}. {data.consistency.limitation}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function PostsTable({ rows }: { rows: PostInsight[] }) {
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">No posts have been read from Instagram yet. Press Read now above.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr>
            <th className="py-2 pr-3 font-medium">Post</th>
            <th className="py-2 pr-3 font-medium">Reached</th>
            <th className="py-2 pr-3 font-medium">Views</th>
            <th className="py-2 pr-3 font-medium">Saves</th>
            <th className="py-2 pr-3 font-medium">Shares</th>
            <th className="py-2 pr-3 font-medium" title="Likes + comments + saves + shares, divided by accounts reached">
              Engagement by reach
            </th>
          </tr>
        </thead>
        <tbody>
          {rows
            .filter((r) => r.kind !== "story")
            .map((r) => (
              <tr key={r.external_id} className="border-t align-top">
                <td className="max-w-[260px] py-2 pr-3">
                  <p className="truncate font-medium">{r.title ?? (r.caption || "Post")}</p>
                  <p className="text-xs text-muted-foreground">
                    {r.kind} · {r.posted_at ? formatInZone(r.posted_at, ZONE) : "date unknown"}
                    {r.permalink && (
                      <a href={r.permalink} target="_blank" rel="noreferrer" aria-label="Open the post on Instagram" className="ml-1 inline-block align-middle">
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </p>
                  {!r.insights_read && <p className="text-xs text-muted-foreground">Figures not read yet</p>}
                </td>
                <td className="py-2 pr-3">{r.insights_read ? formatNumber(r.metrics.reach ?? null) : NOT_AVAILABLE}</td>
                <td className="py-2 pr-3">{r.insights_read ? formatNumber(r.metrics.views ?? null) : NOT_AVAILABLE}</td>
                <td className="py-2 pr-3">{r.insights_read ? formatNumber(r.metrics.saved ?? null) : NOT_AVAILABLE}</td>
                <td className="py-2 pr-3">{r.insights_read ? formatNumber(r.metrics.shares ?? null) : NOT_AVAILABLE}</td>
                <td className="py-2 pr-3">{formatRate(r.er_reach)}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

function Definitions() {
  const [open, setOpen] = useState(false);
  const defs = useMetricDefinitions(open);
  return (
    <div className="space-y-2">
      <Button size="sm" variant="ghost" onClick={() => setOpen(!open)}>
        {open ? "Hide" : "Show"} what every number means
      </Button>
      {open &&
        (defs.isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">{defs.data?.pooled_note}</p>
            {defs.data?.metrics.map((m) => (
              <div key={`${m.scope}-${m.key}`} className="rounded-md border p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{m.label}</span>
                  <Badge variant="outline">{m.scope === "account" ? "Whole profile" : "Single post"}</Badge>
                  <Badge variant={m.kind === "observed" ? "secondary" : "info"}>{KIND_LABEL[m.kind]}</Badge>
                </div>
                <p className="mt-1">{m.definition}</p>
                <p className="text-xs text-muted-foreground">
                  Source: {m.source} · Period: {m.period}
                  {m.limitation ? ` · Limits: ${m.limitation}` : ""}
                </p>
              </div>
            ))}
          </div>
        ))}
    </div>
  );
}

/** Instagram's own figures for the profile and its posts, each with its source, period and whether it is observed or calculated. */
export function AnalyticsTab() {
  const [days, setDays] = useState<number>(28);
  const [group, setGroup] = useState<keyof typeof GROUP_LABEL>("kind");
  const me = useMyRoles();
  const posts = useAnalyticsPosts();
  const canManage = (me.data?.is_superuser ?? false) || (me.data?.effective_permissions ?? []).includes("social_media.manage");
  return (
    <div className="space-y-6">
      <Status canManage={canManage} />
      <div className="flex items-center gap-1" role="group" aria-label="Period">
        {PERIODS.map((p) => (
          <Button key={p} size="sm" variant={days === p ? "default" : "outline"} onClick={() => setDays(p)}>
            Last {p} days
          </Button>
        ))}
      </div>
      <Cards days={days} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Posts</CardTitle>
          <CardDescription>{posts.data?.note ?? "Each post's own figures, as of the last read."}</CardDescription>
        </CardHeader>
        <CardContent>{posts.isLoading ? <Skeleton className="h-24 w-full" /> : posts.isError ? <p className="text-sm text-destructive">Couldn&apos;t load posts.</p> : <PostsTable rows={posts.data?.items ?? []} />}</CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">What seems to work, by group</CardTitle>
          <CardDescription>
            Compare formats, topics, hook styles, calls to action and posting times. Numbers in brackets are how many posts are behind each figure. Small groups are marked: a handful of posts can&apos;t show what works. {posts.data?.pooled_note}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex max-w-full gap-1 overflow-x-auto" role="group" aria-label="Group posts by">
            {(Object.keys(GROUP_LABEL) as (keyof typeof GROUP_LABEL)[]).map((key) => (
              <Button key={key} size="sm" variant={group === key ? "default" : "outline"} onClick={() => setGroup(key)}>
                {GROUP_LABEL[key]}
              </Button>
            ))}
          </div>
          {posts.data && <GroupTable rows={posts.data.breakdowns[group as "kind"] ?? []} />}
        </CardContent>
      </Card>

      <HashtagPanel />

      <Definitions />
    </div>
  );
}
