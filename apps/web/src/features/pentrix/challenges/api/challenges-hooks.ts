import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ChallengeCreatePayload,
  type ChallengeUpdatePayload,
  challengesApi,
} from "@/features/pentrix/challenges/api/challenges-api";

const challengesKey = (category?: string) => ["pentrix", "challenges", category ?? "all"] as const;
const challengeDetailKey = (id: string) => ["pentrix", "challenges", "detail", id] as const;

export function useChallenges(category?: string) {
  return useQuery({
    queryKey: challengesKey(category),
    queryFn: () => challengesApi.list(category),
  });
}

export function useChallenge(id: string | undefined) {
  return useQuery({
    queryKey: challengeDetailKey(id ?? ""),
    queryFn: () => challengesApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateChallenge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ChallengeCreatePayload) => challengesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pentrix", "challenges"] }),
  });
}

export function useUpdateChallenge(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ChallengeUpdatePayload) => challengesApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pentrix", "challenges"] }),
  });
}

export function useDeleteChallenge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => challengesApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pentrix", "challenges"] }),
  });
}
