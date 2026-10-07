import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { HackathonPublic } from "@/features/hackathons/api/hackathons-api";
import { useStaffLeaderboard, useUpdateHackathon } from "@/features/hackathons/api/hackathons-hooks";
import { LeaderboardShareCard } from "@/features/hackathons/components/leaderboard-share-card";
import { ScoreBarChart } from "@/features/hackathons/components/score-bar-chart";

const MEDAL: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" };

/**
 * The live leaderboard as the organiser sees it (the same bar graph and ranking participants and the public
 * presentation page show, always with member names), with the controls for who else gets to see it: the
 * participants' own view, and the public presentation link.
 */
export function LeaderboardTab({ hackathon }: { hackathon: HackathonPublic }) {
  const { data: board, isLoading } = useStaffLeaderboard(hackathon.id);
  const updateHackathon = useUpdateHackathon(hackathon.id);

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{hackathon.title}</CardTitle>
            <CardDescription>
              {board
                ? `${board.entries.length} team${board.entries.length === 1 ? "" : "s"} ranked by total task score. Updates as scores are awarded.`
                : "Team ranking by total task score."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-52 w-full" />
            ) : board && board.entries.length > 0 ? (
              <div className="space-y-6">
                <ScoreBarChart entries={board.entries} />
                <ol className="divide-y">
                  {board.entries.map((entry) => (
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
              <p className="py-6 text-center text-sm text-muted-foreground">
                No task has been scored yet. Teams appear here as soon as you award a score.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6">
        <LeaderboardShareCard hackathon={hackathon} />
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Participants' view</CardTitle>
            <CardDescription>
              {hackathon.leaderboard_visible
                ? "Participants can see this leaderboard in the student portal."
                : "Hidden: participants can't see the leaderboard right now (you still can)."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={hackathon.leaderboard_visible}
                disabled={updateHackathon.isPending}
                onChange={(e) => updateHackathon.mutate({ leaderboard_visible: e.target.checked })}
              />
              <span>Show the leaderboard to participants</span>
            </label>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
