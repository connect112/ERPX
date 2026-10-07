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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useChangeHackathonStatus,
  useHackathon,
  useHackathonTeams,
  useStaffLeaderboard,
  useTaskSubmissions,
  useUpdateHackathon,
} from "@/features/hackathons/api/hackathons-hooks";
import { ProblemStatementsAdminCard } from "@/features/hackathons/components/problem-statements-admin-card";
import { EventEmailsTab } from "@/features/hackathons/components/event-emails-tab";
import { LeaderboardShareCard } from "@/features/hackathons/components/leaderboard-share-card";
import { ParticipantsCard } from "@/features/hackathons/components/participants-card";
import { ParticipantsTab } from "@/features/hackathons/components/participants-tab";
import { ResubmissionCard } from "@/features/hackathons/components/resubmission-card";
import { SubmissionsTab } from "@/features/hackathons/components/submissions-tab";
import { TeamsTab } from "@/features/hackathons/components/teams-tab";
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
  const { data: submissions } = useTaskSubmissions(hackathonId);
  const { data: leaderboard } = useStaffLeaderboard(hackathonId);
  const unreviewedCount = (submissions ?? []).filter((s) => !s.reviewed).length;
  const changeStatus = useChangeHackathonStatus(hackathonId ?? "");
  const updateHackathon = useUpdateHackathon(hackathonId ?? "");
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

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="participants">Participants</TabsTrigger>
          <TabsTrigger value="emails">Emails</TabsTrigger>
          <TabsTrigger value="teams">
            Teams
            {(teams?.length ?? 0) > 0 && (
              <span className="ml-2 rounded-full bg-muted px-1.5 text-xs font-semibold">{teams?.length}</span>
            )}
          </TabsTrigger>
          <TabsTrigger value="submissions">
            Submissions
            {unreviewedCount > 0 && (
              <span className="ml-2 rounded-full bg-amber-100 px-1.5 text-xs font-semibold text-amber-800">
                {unreviewedCount}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-0">
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

          <ParticipantsCard hackathonId={hackathon.id} />

          <ProblemStatementsAdminCard hackathonId={hackathon.id} />

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
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{team.name}</span>
                        <span className="text-xs text-muted-foreground">
                          {team.member_count} / {hackathon.max_team_size}
                        </span>
                      </div>
                      {team.member_names.length > 0 && (
                        <p className="text-muted-foreground">{team.member_names.join(", ")}</p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        {team.tasks_submitted} task{team.tasks_submitted === 1 ? "" : "s"} submitted · {team.total_score}{" "}
                        points
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="py-4 text-center text-sm text-muted-foreground">No teams yet.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Leaderboard</CardTitle>
              <CardDescription>
                Live ranking by total task score. Participants see it too unless you hide it here.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {leaderboard && leaderboard.entries.length > 0 ? (
                <ol className="space-y-1 text-sm">
                  {leaderboard.entries.map((entry) => (
                    <li key={`${entry.rank}-${entry.team_name}`} className="flex items-center justify-between gap-2">
                      <span>
                        <span className="mr-2 inline-block w-5 text-right font-semibold">{entry.rank}</span>
                        {entry.team_name}
                        <span className="ml-2 text-xs text-muted-foreground">
                          {entry.tasks_scored} scored
                        </span>
                      </span>
                      <span className="font-semibold">{entry.score}</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-sm text-muted-foreground">Nothing scored yet. Teams appear when you award a score.</p>
              )}
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={hackathon.leaderboard_visible}
                  disabled={updateHackathon.isPending}
                  onChange={(e) => updateHackathon.mutate({ leaderboard_visible: e.target.checked })}
                />
                <span>Show the leaderboard to participants</span>
              </label>
            </CardContent>
          </Card>

          <LeaderboardShareCard hackathon={hackathon} />

          <ResubmissionCard hackathon={hackathon} />

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
        </TabsContent>

        <TabsContent value="participants" className="mt-0">
          <ParticipantsTab hackathon={hackathon} />
        </TabsContent>

        <TabsContent value="emails" className="mt-0">
          <EventEmailsTab hackathon={hackathon} />
        </TabsContent>

        <TabsContent value="teams" className="mt-0">
          <TeamsTab hackathon={hackathon} />
        </TabsContent>

        <TabsContent value="submissions" className="mt-0">
          <SubmissionsTab hackathonId={hackathon.id} />
        </TabsContent>
      </Tabs>

      <HackathonFormDialog open={editOpen} onOpenChange={setEditOpen} hackathon={hackathon} />
    </div>
  );
}
