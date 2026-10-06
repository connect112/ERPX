import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useHackathonLeaderboards } from "@/features/hackathons/api/hackathons-hooks";

const MEDAL: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" };

export function HackathonLeaderboardPage() {
  const { data: boards, isLoading } = useHackathonLeaderboards();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Leaderboard</h1>
        <p className="text-sm text-muted-foreground">Team rankings, published by the organisers after judging.</p>
      </div>

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : boards && boards.length > 0 ? (
        boards.map((board) => (
          <Card key={board.hackathon_id}>
            <CardHeader>
              <CardTitle className="text-base">{board.hackathon_title}</CardTitle>
              <CardDescription>
                {board.published
                  ? `${board.entries.length} team${board.entries.length === 1 ? "" : "s"} ranked`
                  : "Results haven't been published yet - check back after judging."}
              </CardDescription>
            </CardHeader>
            {board.published && (
              <CardContent>
                {board.entries.length > 0 ? (
                  <ol className="divide-y">
                    {board.entries.map((entry) => (
                      <li key={`${entry.rank}-${entry.team_name}`} className="flex items-center gap-4 py-3">
                        <span className="w-10 text-center text-xl font-semibold">{MEDAL[entry.rank] ?? entry.rank}</span>
                        <div className="min-w-0 flex-1">
                          <p className="font-medium">{entry.team_name}</p>
                          <p className="truncate text-xs text-muted-foreground">
                            {entry.project_title} · {entry.members.join(", ")}
                          </p>
                        </div>
                        <span className="text-lg font-semibold">{entry.score}</span>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="py-4 text-center text-sm text-muted-foreground">No teams have been scored yet.</p>
                )}
              </CardContent>
            )}
          </Card>
        ))
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">No hackathons to show yet.</p>
      )}
    </div>
  );
}
