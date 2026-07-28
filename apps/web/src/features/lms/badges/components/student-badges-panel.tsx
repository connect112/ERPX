import { Award } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useBadges, useStudentBadges } from "@/features/lms/badges/api/badges-hooks";

export function StudentBadgesPanel({ studentId }: { studentId: string }) {
  const { data: studentBadges, isLoading } = useStudentBadges(studentId);
  const { data: badges } = useBadges();

  const badgeName = (id: string) => badges?.find((b) => b.id === id)?.name ?? id;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Badges</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-12 w-full" />}
        {!isLoading && (studentBadges?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No badges earned yet.</p>
        )}
        {studentBadges?.map((award) => (
          <div key={award.id} className="flex items-center gap-2 rounded-md border p-2">
            <Award className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">{badgeName(award.badge_id)}</span>
            <span className="ml-auto text-xs text-muted-foreground">
              {new Date(award.awarded_at).toLocaleDateString()}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
