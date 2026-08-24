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
      queryClient.invalidateQueries({ queryKey: ["hackathons", hackathonId, "team", "me"] });
    },
  });
}

export function useJoinTeam(hackathonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (teamId: string) => hackathonsApi.joinTeam(hackathonId, teamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hackathons", hackathonId, "team", "me"] });
    },
  });
}

export function useTeamSubmission(hackathonId: string, teamId: string | undefined) {
  return useQuery({
    queryKey: ["hackathons", hackathonId, "team", teamId, "submission"],
    queryFn: () => hackathonsApi.getSubmission(hackathonId, teamId as string),
    enabled: Boolean(teamId),
  });
}

export function useSubmitProject(hackathonId: string, teamId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { title: string; description?: string; repo_url?: string; demo_url?: string }) =>
      hackathonsApi.submitProject(hackathonId, teamId as string, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["hackathons", hackathonId, "team", teamId, "submission"],
      });
    },
  });
}
