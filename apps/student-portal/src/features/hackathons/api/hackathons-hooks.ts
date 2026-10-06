import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hackathonsApi } from "@/features/hackathons/api/hackathons-api";

export function useBrowseHackathons() {
  return useQuery({
    queryKey: ["hackathons", "browse"],
    queryFn: () => hackathonsApi.browse(),
  });
}

export function useMyTeam(hackathonId: string) {
  return useQuery({
    queryKey: ["hackathons", hackathonId, "team", "me"],
    queryFn: () => hackathonsApi.myTeam(hackathonId),
  });
}

export function useBrowseTeams(hackathonId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["hackathons", hackathonId, "teams", "browse"],
    queryFn: () => hackathonsApi.browseTeams(hackathonId),
    enabled,
  });
}

export function useCreateTeam(hackathonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => hackathonsApi.createTeam(hackathonId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hackathons", hackathonId] });
    },
  });
}

export function useJoinTeam(hackathonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (teamId: string) => hackathonsApi.joinTeam(hackathonId, teamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hackathons", hackathonId] });
    },
  });
}

/** The tasks with this team's submission for each. Refetched so scores awarded by staff appear without a reload. */
export function useTasks(hackathonId: string) {
  return useQuery({
    queryKey: ["hackathons", hackathonId, "tasks"],
    queryFn: () => hackathonsApi.tasks(hackathonId),
    refetchInterval: 20_000,
  });
}

export function useSubmitTask(hackathonId: string, taskId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { repoUrl: string; file: File | null }) =>
      hackathonsApi.submitTask(hackathonId, taskId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hackathons", hackathonId, "tasks"] });
      queryClient.invalidateQueries({ queryKey: ["hackathons", "achievements"] });
    },
  });
}

export function useHackathonLeaderboards() {
  return useQuery({
    queryKey: ["hackathons", "leaderboards"],
    queryFn: () => hackathonsApi.leaderboards(),
    // Scores are awarded while people are watching: keep the board current.
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });
}

export function useHackathonAchievements() {
  return useQuery({
    queryKey: ["hackathons", "achievements"],
    queryFn: () => hackathonsApi.achievements(),
    refetchInterval: 30_000,
  });
}
