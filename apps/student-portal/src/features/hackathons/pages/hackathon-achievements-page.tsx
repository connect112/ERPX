import { Award as AwardIcon, FileText, Flag, Medal, Rocket, Trophy } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Award } from "@/features/hackathons/api/hackathons-api";
import { useHackathonAchievements } from "@/features/hackathons/api/hackathons-hooks";

const ICONS: Record<Award["code"], typeof Trophy> = {
  winner: Trophy,
  runner_up: Medal,
  third_place: Medal,
  participant: Flag,
  submitted: Rocket,
  report: FileText,
};

export function HackathonAchievementsPage() {
  const { data: awards, isLoading } = useHackathonAchievements();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Achievements</h1>
        <p className="text-sm text-muted-foreground">What you and your team have earned in the hackathon.</p>
      </div>

      {isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : awards && awards.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {awards.map((award) => {
            const Icon = ICONS[award.code] ?? AwardIcon;
            const podium = award.code === "winner" || award.code === "runner_up" || award.code === "third_place";
            return (
              <Card key={`${award.hackathon_id}-${award.code}`} className={podium ? "border-amber-400" : ""}>
                <CardContent className="flex items-start gap-3 p-4">
                  <span
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
                      podium ? "bg-amber-100 text-amber-700" : "bg-primary/10 text-primary"
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="font-medium">{award.label}</p>
                    <p className="text-sm text-muted-foreground">{award.detail}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{award.hackathon_title}</p>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">
          Nothing yet - join a team in a hackathon to start earning achievements.
        </p>
      )}
    </div>
  );
}
