import { Flag } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useChallenges } from "@/features/pentrix/challenges/api/challenges-hooks";
import { useSolvesForStudent } from "@/features/pentrix/flags/api/flags-hooks";

export function StudentSolvesPanel({ studentId }: { studentId: string }) {
  const { data: solves, isLoading } = useSolvesForStudent(studentId);
  const { data: challenges } = useChallenges();

  const challengeTitle = (id: string) => challenges?.find((c) => c.id === id)?.title ?? id;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Solved Challenges</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-12 w-full" />}
        {!isLoading && (solves?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No challenges solved yet.</p>
        )}
        {solves?.map((solve) => (
          <div key={solve.id} className="flex items-center justify-between rounded-md border p-2">
            <div className="flex items-center gap-2">
              <Flag className="h-4 w-4 text-primary" />
              <span className="text-sm">{challengeTitle(solve.challenge_id)}</span>
            </div>
            <div className="text-right">
              <p className="text-xs font-medium">+{solve.points_awarded}</p>
              <p className="text-xs text-muted-foreground">
                {new Date(solve.solved_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
