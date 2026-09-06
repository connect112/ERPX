import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { pentrixApi } from "@/features/pentrix/api/pentrix-api";

export function useLabs() {
  return useQuery({
    queryKey: ["pentrix", "labs"],
    queryFn: () => pentrixApi.listLabs(),
  });
}

export function useMyInstances(studentId: string | undefined) {
  return useQuery({
    queryKey: ["pentrix", "instances", "me", studentId],
    queryFn: () => pentrixApi.myInstances(studentId as string),
    enabled: Boolean(studentId),
    // Active instances can transition provisioning -> running server-side;
    // poll while this page is open so status/access link show up without
    // a manual refresh.
    refetchInterval: 5000,
  });
}

export function useLaunchLab(studentId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (labId: string) => pentrixApi.launchLab(labId, studentId as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pentrix", "instances", "me", studentId] });
    },
  });
}

export function useStopInstance(studentId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (instanceId: string) => pentrixApi.stopInstance(instanceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pentrix", "instances", "me", studentId] });
    },
  });
}

export function useChallenges() {
  return useQuery({
    queryKey: ["pentrix", "challenges"],
    queryFn: () => pentrixApi.listChallenges(),
  });
}

export function useMySolves(studentId: string | undefined) {
  return useQuery({
    queryKey: ["pentrix", "solves", "me", studentId],
    queryFn: () => pentrixApi.mySolves(studentId as string),
    enabled: Boolean(studentId),
  });
}

export function useSubmitFlag(studentId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ challengeId, flagValue }: { challengeId: string; flagValue: string }) =>
      pentrixApi.submitFlag(challengeId, studentId as string, flagValue),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pentrix", "solves", "me", studentId] });
      queryClient.invalidateQueries({ queryKey: ["pentrix", "leaderboard"] });
      queryClient.invalidateQueries({ queryKey: ["pentrix", "achievements", "me", studentId] });
    },
  });
}
