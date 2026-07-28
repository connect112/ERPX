import { ArrowLeft, Pencil } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useChangeHackathonStatus,
  useHackathon,
  useHackathonSubmissions,
  useHackathonTeams,
} from "@/features/hackathons/api/hackathons-hooks";
import { GradeSubmissionRow } from "@/features/hackathons/components/grade-submission-row";
import { HackathonFormDialog } from "@/features/hackathons/components/hackathon-form-dialog";
import { HackathonStatusBadge } from "@/features/hackathons/components/hackathon-status-badge";
import {
  type HackathonStatus,
  hackathonStatusLabels,
  hackathonStatusValues,
} from "@/features/hackathons/schemas/hackathon-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function HackathonDetailPage() {
  const { hackathonId } = useParams<{ hackathonId: string }>();
  const navigate = useNavigate();
  const { data: hackathon, isLoading } = useHackathon(hackathonId);
  const { data: teams, isLoading: teamsLoading } = useHackathonTeams(hackathonId);
  const { data: submissions, isLoading: submissionsLoading } = useHackathonSubmissions(hackathonId);
  const changeStatus = useChangeHackathonStatus(hackathonId ?? "");
  const [editOpen, setEditOpen] = useState(false);

  if (isLoading || !hackathon) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/hackathons")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{hackathon.title}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{hackathon.code}</span>
              <HackathonStatusBadge status={hackathon.status} />
            </div>
          </div>
        </div>
        <Button variant="outline" onClick={() => setEditOpen(true)}>
          <Pencil className="h-4 w-4" />
          Edit
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Hackathon details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Theme" value={hackathon.theme || "—"} />
              <DetailRow
                label="Registration deadline"
                value={new Date(hackathon.registration_deadline).toLocaleDateString()}
              />
              <DetailRow label="Start date" value={new Date(hackathon.start_date).toLocaleDateString()} />
              <DetailRow label="End date" value={new Date(hackathon.end_date).toLocaleDateString()} />
              <DetailRow label="Max team size" value={hackathon.max_team_size} />
              <DetailRow
                label="Prize pool"
                value={hackathon.prize_pool != null ? hackathon.prize_pool.toLocaleString() : "—"}
              />
              {hackathon.description && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Description</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{hackathon.description}</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Teams</CardTitle>
              <CardDescription>{teams?.length ?? 0} teams registered.</CardDescription>
            </CardHeader>
            <CardContent>
              {teamsLoading ? (
                <Skeleton className="h-16 w-full" />
              ) : teams && teams.length > 0 ? (
                <ul className="divide-y">
                  {teams.map((team) => (
                    <li key={team.id} className="py-2 text-sm">
                      {team.name}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="py-4 text-center text-sm text-muted-foreground">No teams yet.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Submissions</CardTitle>
              <CardDescription>Review and grade each team's project.</CardDescription>
            </CardHeader>
            <CardContent>
              {submissionsLoading ? (
                <Skeleton className="h-24 w-full" />
              ) : submissions && submissions.length > 0 ? (
                <div>
                  {submissions.map((submission) => (
                    <GradeSubmissionRow
                      key={submission.id}
                      hackathonId={hackathon.id}
                      submission={submission}
                      team={teams?.find((t) => t.id === submission.team_id)}
                    />
                  ))}
                </div>
              ) : (
                <p className="py-4 text-center text-sm text-muted-foreground">No submissions yet.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Change status</CardTitle>
            </CardHeader>
            <CardContent>
              <Select
                value={hackathon.status}
                onValueChange={(value) => changeStatus.mutate(value as HackathonStatus)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {hackathonStatusValues.map((s) => (
                    <SelectItem key={s} value={s}>
                      {hackathonStatusLabels[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        </div>
      </div>

      <HackathonFormDialog open={editOpen} onOpenChange={setEditOpen} hackathon={hackathon} />
    </div>
  );
}
