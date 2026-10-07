import { Maximize2 } from "lucide-react";
import { useEffect } from "react";
import { useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePublicLeaderboard } from "@/features/hackathons/api/hackathons-hooks";
import { ScoreBarChart } from "@/features/hackathons/components/score-bar-chart";

const MEDAL: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" };

/**
 * The shared live leaderboard: the same look as the student portal's Leaderboard page (bar graph, then the
 * ranked list), without the sidebar or a login, for showing on a screen. Refreshes by itself.
 */
export function PublicLeaderboardPage() {
  const { slug = "" } = useParams<{ slug: string }>();
  const { data, isError, isLoading, dataUpdatedAt } = usePublicLeaderboard(slug);
  const title = data?.title;

  useEffect(() => {
    document.title = title ? `${title} - leaderboard` : "Leaderboard";
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex";
    document.head.appendChild(meta);
    return () => {
      meta.remove();
    };
  }, [title]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-emerald-600">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              Live
            </p>
            <h1 className="text-2xl font-semibold">Leaderboard</h1>
            <p className="text-sm text-muted-foreground">
              Team ranking by total task score. It updates as the organisers award scores.
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {dataUpdatedAt > 0 && <span>Updated {new Date(dataUpdatedAt).toLocaleTimeString()}</span>}
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                if (document.fullscreenElement) void document.exitFullscreen();
                else void document.documentElement.requestFullscreen?.();
              }}
            >
              <Maximize2 className="h-4 w-4" />
              Full screen
            </Button>
          </div>
        </div>

        {isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : isError || !data ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">This leaderboard link isn't available</CardTitle>
              <CardDescription>
                It may have been turned off or changed. Ask the organisers for the current link.
              </CardDescription>
            </CardHeader>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{data.title}</CardTitle>
              <CardDescription>
                {data.entries.length} team{data.entries.length === 1 ? "" : "s"} ranked
              </CardDescription>
            </CardHeader>
            <CardContent>
              {data.entries.length > 0 ? (
                <div className="space-y-6">
                  <ScoreBarChart entries={data.entries} maxTotal={data.max_total} />
                  <ol className="divide-y">
                    {data.entries.map((entry) => (
                      <li key={`${entry.rank}-${entry.team_name}`} className="flex items-center gap-4 py-3">
                        <span className="w-10 text-center text-xl font-semibold">{MEDAL[entry.rank] ?? entry.rank}</span>
                        <div className="min-w-0 flex-1">
                          <p className="font-medium">{entry.team_name}</p>
                          <p className="truncate text-xs text-muted-foreground">
                            {entry.tasks_scored} task{entry.tasks_scored === 1 ? "" : "s"} scored
                            {entry.members.length > 0 && ` · ${entry.members.join(", ")}`}
                          </p>
                        </div>
                        <span className="text-lg font-semibold">{entry.score}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  No task has been scored yet. Teams appear here as soon as a score is awarded.
                </p>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
