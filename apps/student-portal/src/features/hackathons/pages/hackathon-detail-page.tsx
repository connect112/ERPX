import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useBrowseHackathons,
  useCreateTeam,
  useJoinTeamWithCode,
  useMyTeam,
} from "@/features/hackathons/api/hackathons-hooks";
import { EventTimer } from "@/features/hackathons/components/event-timer";
import { TasksSection } from "@/features/hackathons/components/tasks-section";

// The server's reason (name already taken, team full, registration closed...)
// is what a student needs to see; a silent failure just looks like a broken button.
function errorText(error: unknown, fallback: string): string {
  return (
    (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? fallback
  );
}

export function HackathonDetailPage() {
  const { hackathonId } = useParams<{ hackathonId: string }>();
  const id = hackathonId as string;
  const { data: hackathons } = useBrowseHackathons();
  const hackathon = hackathons?.find((h) => h.id === id);
  const maxTeamSize = hackathon?.max_team_size ?? 4;

  const { data: myTeam, isLoading: myTeamLoading } = useMyTeam(id);
  const createTeam = useCreateTeam(id);
  const joinTeam = useJoinTeamWithCode(id);

  const [teamName, setTeamName] = useState("");
  const [teamCode, setTeamCode] = useState("");
  const [copied, setCopied] = useState(false);

  if (myTeamLoading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">{hackathon ? `${hackathon.title} - your team` : "Your Team"}</h1>
        {hackathon && (hackathon.timer_starts_at || hackathon.timer_ends_at) && (
          <EventTimer startsAt={hackathon.timer_starts_at} endsAt={hackathon.timer_ends_at} />
        )}
        <p className="text-sm text-muted-foreground">
          Create a team, or join your teammates' team with its team code (up to {maxTeamSize} people per team).
        </p>
      </div>

      {!myTeam ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Create a team</CardTitle>
              <CardDescription>
                You'll be the first member. Your team gets a code to share with your teammates so they can join.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input placeholder="Team name" value={teamName} onChange={(e) => setTeamName(e.target.value)} />
              <Button
                className="w-full"
                disabled={!teamName.trim() || createTeam.isPending}
                onClick={() => createTeam.mutate(teamName.trim())}
              >
                {createTeam.isPending ? "Creating…" : "Create team"}
              </Button>
              {createTeam.isError && (
                <p className="text-sm text-destructive">{errorText(createTeam.error, "Could not create the team.")}</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Join an existing team</CardTitle>
              <CardDescription>Ask a teammate for the team code (it is shown on their team page) and enter it here.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (teamCode.trim() && !joinTeam.isPending) joinTeam.mutate(teamCode.trim());
                }}
              >
                <Input
                  placeholder="Team code, e.g. K7M4QX"
                  value={teamCode}
                  onChange={(e) => setTeamCode(e.target.value.toUpperCase())}
                  maxLength={16}
                  autoComplete="off"
                  aria-label="Team code"
                  className="font-mono uppercase tracking-widest"
                />
                <Button className="w-full" type="submit" disabled={!teamCode.trim() || joinTeam.isPending}>
                  {joinTeam.isPending ? "Joining…" : "Join team"}
                </Button>
              </form>
              {joinTeam.isError && (
                <p className="text-sm text-destructive">{errorText(joinTeam.error, "Could not join the team.")}</p>
              )}
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{myTeam.team.name}</CardTitle>
            <CardDescription>{myTeam.members.length} member(s)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-1 text-sm">
              {myTeam.members.map((member) => (
                <li key={member.id}>{member.student_name}</li>
              ))}
            </ul>
            <div className="rounded-md border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground">
                Team code: share it with teammates so they can join (only your team and the organisers can see it).
              </p>
              <div className="mt-1 flex items-center gap-3">
                <span className="font-mono text-2xl font-semibold tracking-[0.3em]" aria-label="Team code">
                  {myTeam.team.join_code}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    void navigator.clipboard?.writeText(myTeam.team.join_code).then(() => {
                      setCopied(true);
                      window.setTimeout(() => setCopied(false), 1500);
                    });
                  }}
                >
                  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <TasksSection hackathonId={id} />
    </div>
  );
}
