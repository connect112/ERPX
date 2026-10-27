import { Trophy } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TeamPerformance } from "@/features/our-internships/api/our-internships-api";
import { formatMarks, formatScore, formatTeamScore } from "@/features/our-internships/lib/performance";

/**
 * The hackathon teams side by side: each team's score and rank, and each member's exam marks and individual score, so a
 * strong team can be compared with another and its members selected together or one by one.
 */
export function TeamWiseView({
  teams,
  showInstitution,
  pending,
  onSelect,
}: {
  teams: TeamPerformance[];
  showInstitution: boolean;
  pending: boolean;
  onSelect: (studentIds: string[]) => void;
}) {
  if (teams.length === 0) {
    return (
      <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">
        No hackathon teams to show. Teams appear once a hackathon is linked to the event and people have formed teams. The
        Students tab lists everyone either way.
      </p>
    );
  }
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {teams.map((t) => {
        const open = t.members.filter((m) => m.student_id && !m.selected).map((m) => m.student_id as string);
        const key = `${t.event_id}-${t.team_id ?? "none"}`;
        return (
          <Card key={key}>
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    {t.rank === 1 && <Trophy className="h-4 w-4 text-amber-500" aria-label="Top team" />}
                    {t.team_name}
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {showInstitution ? `${t.institution_name} · ` : ""}
                    {t.event_name}
                    {t.hackathon_title ? ` · ${t.hackathon_title}` : ""}
                  </p>
                </div>
                {t.team_id && (
                  <div className="text-right">
                    <p className="text-sm font-semibold">{t.tasks_scored > 0 ? formatTeamScore(t.score, t.max_total, t.rank) : "Not scored"}</p>
                    <p className="text-xs text-muted-foreground">team score</p>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              <ul className="divide-y rounded-md border">
                {t.members.map((m) => (
                  <li key={`${m.email}-${m.name}`} className="flex items-center justify-between gap-3 p-2 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-medium">
                        {m.name}
                        {m.selected && (
                          <Badge variant="success" className="ml-2">
                            Selected
                          </Badge>
                        )}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        Exam {formatMarks(m.exam_score, m.exam_total)} · Individual {formatScore(m.individual_score)}
                        {!m.student_id && " · not on this event's registration list"}
                      </p>
                    </div>
                    {m.student_id && !m.selected && (
                      <Button size="sm" variant="outline" disabled={pending} onClick={() => onSelect([m.student_id as string])}>
                        Select
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
              {open.length > 1 && (
                <Button size="sm" disabled={pending} onClick={() => onSelect(open)}>
                  Select all {open.length} members
                </Button>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
