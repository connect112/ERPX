import { Trophy } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useLeaderboard } from "@/features/pentrix/leaderboard/api/leaderboard-hooks";

const medalColors = ["text-amber-500", "text-slate-400", "text-amber-700"];

export function LeaderboardPage() {
  const { data: entries, isLoading, isError } = useLeaderboard();

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Leaderboard</h1>
        <p className="mt-1 text-muted-foreground">
          Ranked by net score — points earned from solves minus points spent unlocking hints.
        </p>
      </div>

      <Card>
        <CardContent className="p-6">
          {isLoading && <Skeleton className="h-64 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load leaderboard.</p>
          )}
          {!isLoading && !isError && (entries?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No solves recorded yet. The leaderboard will populate as students solve challenges.
            </p>
          )}
          {!isLoading && !isError && (entries?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">Rank</TableHead>
                  <TableHead>Student</TableHead>
                  <TableHead>Solved</TableHead>
                  <TableHead>Earned</TableHead>
                  <TableHead>Spent on hints</TableHead>
                  <TableHead>Net score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries?.map((entry, index) => (
                  <TableRow key={entry.student_id}>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {index < 3 ? (
                          <Trophy className={`h-4 w-4 ${medalColors[index]}`} />
                        ) : (
                          <span className="text-sm text-muted-foreground">{index + 1}</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="font-medium">
                      {entry.student_name}
                      <span className="ml-2 font-mono text-xs text-muted-foreground">
                        {entry.student_code}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{entry.challenges_solved}</TableCell>
                    <TableCell className="text-muted-foreground">{entry.points_earned}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {entry.points_spent_on_hints}
                    </TableCell>
                    <TableCell className="font-semibold">{entry.net_score}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
