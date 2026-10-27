import { Award } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { type MyAward, useMyAwards } from "@/features/my-internship/api/my-internship-api";
import { formatDateTime } from "@/features/my-internship/lib/format";

function AwardCard({ award, showInternship }: { award: MyAward; showInternship: boolean }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Award className="h-5 w-5 text-amber-500" />
          {award.name}
        </CardTitle>
        <CardDescription>
          {showInternship ? `${award.internship_title} · ` : ""}
          {formatDateTime(award.granted_at)}
        </CardDescription>
      </CardHeader>
      {(award.description || award.note) && (
        <CardContent className="space-y-1 text-sm">
          {award.description && <p className="text-muted-foreground">{award.description}</p>}
          {award.note && <p>{award.note}</p>}
        </CardContent>
      )}
    </Card>
  );
}

/** The awards a student holds on one internship. */
export function AwardsSection({ internshipId }: { internshipId: string }) {
  const { data, isLoading, isError } = useMyAwards();
  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (isError) return <p className="text-sm text-destructive">Could not load your awards.</p>;
  const mine = (data ?? []).filter((a) => a.internship_id === internshipId);
  if (mine.length === 0) return <p className="rounded-md border bg-card p-8 text-center text-sm text-muted-foreground">You have not received an award yet.</p>;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {mine.map((a) => (
        <AwardCard key={a.id} award={a} showInternship={false} />
      ))}
    </div>
  );
}

/** Awards across all internships, for the dashboard. Shows nothing until the student has one. */
export function AwardsOnProfile() {
  const { data } = useMyAwards();
  if (!data || data.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">My awards</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.map((a) => (
          <AwardCard key={a.id} award={a} showInternship />
        ))}
      </div>
    </section>
  );
}
