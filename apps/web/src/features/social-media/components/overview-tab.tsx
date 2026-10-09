import { AlertTriangle, CheckCircle2, Circle, Info, ListChecks } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useOverview } from "@/features/social-media/api/social-media-hooks";
import { STATUS_LABEL } from "@/features/social-media/lib/format";
import type { PostStatus } from "@/features/social-media/api/social-media-api";

const COUNTED: PostStatus[] = ["draft", "review", "approved", "scheduled", "published", "failed"];

interface Props {
  onOpenTab: (tab: string, status?: string) => void;
}

export function OverviewTab({ onOpenTab }: Props) {
  const overview = useOverview();

  if (overview.isLoading) return <Skeleton className="h-64 w-full" />;
  if (overview.isError || !overview.data) return <p className="text-sm text-destructive">Couldn&apos;t load the briefing. Try again in a moment.</p>;
  const data = overview.data;

  function open(link: string | null) {
    if (!link) return;
    const [tab, query] = link.split("?");
    onOpenTab(tab, query?.startsWith("status=") ? query.slice(7) : undefined);
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Daily briefing</CardTitle>
          <CardDescription>What needs your attention right now.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {data.briefing.map((item, i) => (
            <div key={i} className="flex items-start gap-3 rounded-md border p-3 text-sm">
              {item.level === "warning" ? (
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden />
              ) : item.level === "action" ? (
                <ListChecks className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
              ) : (
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
              )}
              <span className="flex-1">{item.message}</span>
              {item.link && (
                <Button size="sm" variant="outline" onClick={() => open(item.link)}>
                  Open
                </Button>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {COUNTED.map((status) => (
          <Card key={status}>
            <CardContent className="p-4">
              <p className="text-2xl font-semibold">{data.post_counts[status] ?? 0}</p>
              <p className="text-xs text-muted-foreground">{STATUS_LABEL[status]}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Waiting for approval</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {data.awaiting_approval.length === 0 ? (
              <p className="text-muted-foreground">Nothing is waiting.</p>
            ) : (
              data.awaiting_approval.map((post) => (
                <div key={post.id} className="flex items-center justify-between gap-2 rounded-md border p-2">
                  <span className="truncate">{post.title}</span>
                  <Button size="sm" variant="outline" onClick={() => onOpenTab("posts", "review")}>
                    Review
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Leads from social media</CardTitle>
            <CardDescription>From the CRM, last 30 days.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p className="text-2xl font-semibold">{data.leads.last_30_days}</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(data.leads.by_status).map(([status, count]) => (
                <Badge key={status} variant="secondary">
                  {status}: {count}
                </Badge>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">{data.leads.note}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>What is built, and what is next</CardTitle>
          <CardDescription>
            This page grows in phases. Features that aren&apos;t built yet are listed here instead of shown as buttons that do nothing.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {data.roadmap.map((item) => (
            <div key={item.phase} className="flex items-start gap-3 text-sm">
              {item.status === "done" ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
              ) : (
                <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
              )}
              <span>
                <span className="font-medium">Phase {item.phase}:</span> {item.title}
                {item.status === "next" && <Badge className="ml-2" variant="info">Next</Badge>}
              </span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
