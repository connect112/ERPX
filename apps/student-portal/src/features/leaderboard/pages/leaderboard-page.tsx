import { Trophy } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useMyStudentProfile } from "@/features/dashboard/api/student-hooks";
import { useLeaderboard } from "@/features/leaderboard/api/leaderboard-hooks";

export function LeaderboardPage() {
  const { data: student } = useMyStudentProfile();
  const { data: entries, isLoading } = useLeaderboard();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Leaderboard</h1>
        <p className="text-sm text-muted-foreground">
          Ranked by net score — challenge points earned, minus points spent unlocking hints.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Pentrix Cyber Range Rankings</CardTitle>
          <CardDescription>Your row is highlighted.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-2 p-6">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : entries && entries.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">Rank</TableHead>
                  <TableHead>Student</TableHead>
                  <TableHead className="text-right">Solved</TableHead>
                  <TableHead className="text-right">Earned</TableHead>
                  <TableHead className="text-right">Spent on hints</TableHead>
                  <TableHead className="text-right">Net score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((entry, index) => (
                  <TableRow
                    key={entry.student_id}
                    className={cn(entry.student_id === student?.id && "bg-primary/5")}
                  >
                    <TableCell className="font-medium">
                      {index === 0 ? (
                        <Trophy className="h-4 w-4 text-amber-500" />
                      ) : (
                        index + 1
                      )}
                    </TableCell>
                    <TableCell>
                      {entry.student_name}
                      <span className="ml-2 text-xs text-muted-foreground">{entry.student_code}</span>
                    </TableCell>
                    <TableCell className="text-right">{entry.challenges_solved}</TableCell>
                    <TableCell className="text-right">{entry.points_earned}</TableCell>
                    <TableCell className="text-right">{entry.points_spent_on_hints}</TableCell>
                    <TableCell className="text-right font-semibold">{entry.net_score}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="p-6 text-center text-sm text-muted-foreground">
              No solves yet — be the first on the board.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
