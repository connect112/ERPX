import { format, parseISO } from "date-fns";
import { Award, Medal } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyStudentProfile } from "@/features/dashboard/api/student-hooks";
import {
  useAchievementCatalog,
  useMyAchievements,
  useMyCertifications,
} from "@/features/achievements/api/achievements-hooks";

export function AchievementsPage() {
  const { data: student } = useMyStudentProfile();
  const { data: catalog, isLoading: catalogLoading } = useAchievementCatalog();
  const { data: earned, isLoading: earnedLoading } = useMyAchievements(student?.id);
  const { data: certifications, isLoading: certificationsLoading } = useMyCertifications(student?.id);

  const catalogById = new Map((catalog ?? []).map((a) => [a.id, a]));
  const earnedLoadingAny = catalogLoading || earnedLoading;

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Achievements & Certifications</h1>
        <p className="text-sm text-muted-foreground">
          Badges you've earned in the Pentrix cyber range, and certifications issued to you.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Medal className="h-4 w-4" /> Achievements
          </CardTitle>
          <CardDescription>Earned automatically as you solve challenges.</CardDescription>
        </CardHeader>
        <CardContent>
          {earnedLoadingAny ? (
            <div className="space-y-2">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : earned && earned.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {earned.map((studentAchievement) => {
                const achievement = catalogById.get(studentAchievement.achievement_id);
                return (
                  <div
                    key={studentAchievement.id}
                    className="flex items-start gap-3 rounded-lg border p-4"
                  >
                    <Medal className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
                    <div>
                      <p className="font-medium">{achievement?.name ?? "Achievement"}</p>
                      {achievement?.description && (
                        <p className="text-sm text-muted-foreground">{achievement.description}</p>
                      )}
                      <p className="mt-1 text-xs text-muted-foreground">
                        Awarded {format(parseISO(studentAchievement.awarded_at), "PP")}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No achievements yet — solve a challenge in the Cyber Range to earn your first badge.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Award className="h-4 w-4" /> Certifications
          </CardTitle>
          <CardDescription>Issued once you meet a track's point threshold.</CardDescription>
        </CardHeader>
        <CardContent>
          {certificationsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-14 w-full" />
            </div>
          ) : certifications && certifications.length > 0 ? (
            <ul className="divide-y">
              {certifications.map((cert) => (
                <li key={cert.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="font-medium">{cert.track_name}</p>
                    <p className="text-sm text-muted-foreground">
                      Certificate #{cert.certificate_number} · {cert.points_at_issuance} pts
                    </p>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {format(parseISO(cert.issued_at), "PP")}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No certifications issued yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
