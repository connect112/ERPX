import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useHackathonLeaderboards } from "@/features/hackathons/api/hackathons-hooks";
import { ScoreBarChart } from "@/features/hackathons/components/score-bar-chart";

const MEDAL: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" };

export function HackathonLeaderboardPage() {
  const { data: boards, isLoading } = useHackathonLeaderboards();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Leaderboard</h1>
        <p className="text-sm text-muted-foreground">
          Team ranking by total task score. It updates as the organisers award
          scores.
        </p>
      </div>

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : boards && boards.length > 0 ? (
        boards.map((board) => (
          <Card key={board.hackathon_id}>
            <CardHeader>
              <CardTitle className="text-base">
                {board.hackathon_title}
              </CardTitle>
              <CardDescription>
                {board.published
                  ? `${board.entries.length} team${board.entries.length === 1 ? "" : "s"} ranked`
                  : "The organisers are not showing the leaderboard right now."}
              </CardDescription>
            </CardHeader>
            {board.published && (
              <CardContent>
                {board.entries.length > 0 ? (
                  <div className="space-y-6">
                    <ScoreBarChart entries={board.entries} />
                    <ol className="divide-y">
                      {board.entries.map((entry) => (
                        <li
                          key={`${entry.rank}-${entry.team_name}`}
                          className="flex items-center gap-4 py-3"
                        >
                          <span className="w-10 text-center text-xl font-semibold">
                            {MEDAL[entry.rank] ?? entry.rank}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="font-medium">{entry.team_name}</p>
                            <p className="truncate text-xs text-muted-foreground">
                              {entry.tasks_scored} task
                              {entry.tasks_scored === 1 ? "" : "s"} scored ·{" "}
                              {entry.members.join(", ")}
                            </p>
                          </div>
                          <span className="text-lg font-semibold">
                            {entry.score}
                          </span>
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : (
                  <p className="py-4 text-center text-sm text-muted-foreground">
                    No task has been scored yet. Teams appear here as soon as a
                    score is awarded.
                  </p>
                )}
              </CardContent>
            )}
          </Card>
        ))
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No hackathons to show yet.
        </p>
      )}
    </div>
  );
}
