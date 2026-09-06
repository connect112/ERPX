import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useMyStudentProfile } from "@/features/dashboard/api/student-hooks";
import { ChallengeCard } from "@/features/pentrix/components/challenge-card";
import { LabCard } from "@/features/pentrix/components/lab-card";
import {
  useChallenges,
  useLabs,
  useLaunchLab,
  useMyInstances,
  useMySolves,
  useStopInstance,
  useSubmitFlag,
} from "@/features/pentrix/api/pentrix-hooks";

export function CyberRangePage() {
  const { data: student } = useMyStudentProfile();
  const studentId = student?.id;

  const { data: labs, isLoading: labsLoading } = useLabs();
  const { data: instances } = useMyInstances(studentId);
  const launchLab = useLaunchLab(studentId);
  const stopInstance = useStopInstance(studentId);

  const { data: challenges, isLoading: challengesLoading } = useChallenges();
  const { data: solves } = useMySolves(studentId);
  const submitFlag = useSubmitFlag(studentId);

  const activeInstanceByLab = new Map(
    (instances ?? [])
      .filter((i) => i.status === "running" || i.status === "provisioning")
      .map((i) => [i.lab_id, i])
  );
  const solvedChallengeIds = new Set((solves ?? []).map((s) => s.challenge_id));

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Cyber Range</h1>
        <p className="text-sm text-muted-foreground">
          Launch a lab, work through it, and submit flags for challenges as you solve them.
        </p>
      </div>

      <Tabs defaultValue="labs">
        <TabsList>
          <TabsTrigger value="labs">Labs</TabsTrigger>
          <TabsTrigger value="challenges">Challenges</TabsTrigger>
        </TabsList>

        <TabsContent value="labs">
          {labsLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Skeleton className="h-48 w-full" />
              <Skeleton className="h-48 w-full" />
              <Skeleton className="h-48 w-full" />
            </div>
          ) : labs && labs.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {labs.map((lab) => (
                <LabCard
                  key={lab.id}
                  lab={lab}
                  activeInstance={activeInstanceByLab.get(lab.id)}
                  isLaunching={launchLab.isPending && launchLab.variables === lab.id}
                  isStopping={stopInstance.isPending}
                  onLaunch={() => launchLab.mutate(lab.id)}
                  onStop={(instanceId) => stopInstance.mutate(instanceId)}
                />
              ))}
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No labs available yet.
            </p>
          )}
        </TabsContent>

        <TabsContent value="challenges">
          {challengesLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : challenges && challenges.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {challenges.map((challenge) => (
                <ChallengeCard
                  key={challenge.id}
                  challenge={challenge}
                  solved={solvedChallengeIds.has(challenge.id)}
                  onSubmit={(flagValue) =>
                    submitFlag.mutateAsync({ challengeId: challenge.id, flagValue })
                  }
                />
              ))}
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No challenges available yet.
            </p>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
