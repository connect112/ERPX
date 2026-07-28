import { Trophy } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAchievements,
  useStudentAchievements,
} from "@/features/pentrix/achievements/api/achievements-hooks";

export function StudentAchievementsPanel({ studentId }: { studentId: string }) {
  const { data: earned, isLoading } = useStudentAchievements(studentId);
  const { data: achievements } = useAchievements();

  const achievementName = (id: string) => achievements?.find((a) => a.id === id)?.name ?? id;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Achievements</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-12 w-full" />}
        {!isLoading && (earned?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No achievements earned yet.</p>
        )}
        {earned?.map((award) => (
          <div key={award.id} className="flex items-center gap-2 rounded-md border p-2">
            <Trophy className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">{achievementName(award.achievement_id)}</span>
            <span className="ml-auto text-xs text-muted-foreground">
              {new Date(award.awarded_at).toLocaleDateString()}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
