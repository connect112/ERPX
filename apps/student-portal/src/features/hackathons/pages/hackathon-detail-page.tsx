import { useState } from "react";
import { useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ProblemStatementsCard } from "@/features/hackathons/components/problem-statements-card";
import { ReportCard } from "@/features/hackathons/components/report-card";
import {
  useBrowseHackathons,
  useBrowseTeams,
  useCreateTeam,
  useJoinTeam,
  useMyTeam,
  useSubmitProject,
  useTeamSubmission,
} from "@/features/hackathons/api/hackathons-hooks";

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
  const { data: browsableTeams } = useBrowseTeams(id, !myTeamLoading && !myTeam);
  const createTeam = useCreateTeam(id);
  const joinTeam = useJoinTeam(id);

  const [teamName, setTeamName] = useState("");

  const teamId = myTeam?.team.id;
  const { data: submission } = useTeamSubmission(id, teamId);
  const submitProject = useSubmitProject(id, teamId);

  const [projectTitle, setProjectTitle] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [demoUrl, setDemoUrl] = useState("");
  const [description, setDescription] = useState("");

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
      <div>
        <h1 className="text-2xl font-semibold">{hackathon ? `${hackathon.title} - your team` : "Your Team"}</h1>
        <p className="text-sm text-muted-foreground">
          Create a team, or join one that's still recruiting (up to {maxTeamSize} people per team).
        </p>
      </div>

      <ProblemStatementsCard
        hackathonId={id}
        hasTeam={!!myTeam}
        chosenId={myTeam?.team.problem_statement_id ?? null}
      />

      {!myTeam ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Create a team</CardTitle>
              <CardDescription>You'll be the first member. Tell your friends your team name so they can join it.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                placeholder="Team name"
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
              />
              <Button
                className="w-full"
                disabled={!teamName.trim() || createTeam.isPending}
                onClick={() => createTeam.mutate(teamName.trim())}
              >
                {createTeam.isPending ? "Creating…" : "Create team"}
              </Button>
              {createTeam.isError && <p className="text-sm text-destructive">{errorText(createTeam.error, "Could not create the team.")}</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Join an existing team</CardTitle>
              <CardDescription>Teams already formed for this hackathon.</CardDescription>
            </CardHeader>
            <CardContent>
              {browsableTeams && browsableTeams.length > 0 ? (
                <ul className="divide-y">
                  {browsableTeams.map((team) => {
                    const full = team.member_count >= maxTeamSize;
                    return (
                      <li key={team.id} className="flex items-center justify-between py-2">
                        <span className="text-sm font-medium">
                          {team.name}
                          <span className="ml-2 text-xs font-normal text-muted-foreground">
                            {team.member_count}/{maxTeamSize}
                          </span>
                        </span>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={joinTeam.isPending || full}
                          onClick={() => joinTeam.mutate(team.id)}
                        >
                          {full ? "Full" : "Join"}
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  No teams to join yet — be the first to create one.
                </p>
              )}
              {joinTeam.isError && <p className="mt-2 text-sm text-destructive">{errorText(joinTeam.error, "Could not join the team.")}</p>}
            </CardContent>
          </Card>
        </div>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{myTeam.team.name}</CardTitle>
              <CardDescription>{myTeam.members.length} member(s)</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1 text-sm">
                {myTeam.members.map((member) => (
                  <li key={member.id}>{member.student_name}</li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <ReportCard hackathonId={id} report={myTeam.report} />

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Project submission</CardTitle>
              <CardDescription>
                {submission ? "Submitted — you can resubmit to update it." : "Not submitted yet."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="project-title">Title</Label>
                <Input
                  id="project-title"
                  value={projectTitle || submission?.title || ""}
                  onChange={(e) => setProjectTitle(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="project-description">Description</Label>
                <Textarea
                  id="project-description"
                  value={description || submission?.description || ""}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="repo-url">Repository URL</Label>
                  <Input
                    id="repo-url"
                    value={repoUrl || submission?.repo_url || ""}
                    onChange={(e) => setRepoUrl(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="demo-url">Demo URL</Label>
                  <Input
                    id="demo-url"
                    value={demoUrl || submission?.demo_url || ""}
                    onChange={(e) => setDemoUrl(e.target.value)}
                  />
                </div>
              </div>
              {submission?.score !== null && submission?.score !== undefined && (
                <p className="text-sm">
                  Score: <span className="font-semibold">{submission.score}</span>
                  {submission.feedback && ` — ${submission.feedback}`}
                </p>
              )}
              <Button
                disabled={!(projectTitle || submission?.title) || submitProject.isPending}
                onClick={() =>
                  submitProject.mutate({
                    title: projectTitle || submission?.title || "",
                    description: description || submission?.description || undefined,
                    repo_url: repoUrl || submission?.repo_url || undefined,
                    demo_url: demoUrl || submission?.demo_url || undefined,
                  })
                }
              >
                {submitProject.isPending ? "Saving…" : submission ? "Update submission" : "Submit project"}
              </Button>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
