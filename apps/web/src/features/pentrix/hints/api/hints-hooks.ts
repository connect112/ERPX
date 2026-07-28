import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type HintCreatePayload, hintsApi } from "@/features/pentrix/hints/api/hints-api";

const hintsKey = (challengeId: string, studentId: string) =>
  ["pentrix", "hints", challengeId, studentId] as const;

export function useCreateHint(challengeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: HintCreatePayload) => hintsApi.create(challengeId, payload),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["pentrix", "hints", challengeId] }),
  });
}

export function useHintsForStudent(challengeId: string, studentId: string) {
  return useQuery({
    queryKey: hintsKey(challengeId, studentId),
    queryFn: () => hintsApi.listForStudent(challengeId, studentId),
    enabled: !!challengeId && !!studentId,
  });
}

export function useUnlockHint(challengeId: string, studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (hintId: string) => hintsApi.unlock(hintId, studentId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: hintsKey(challengeId, studentId) }),
  });
}
