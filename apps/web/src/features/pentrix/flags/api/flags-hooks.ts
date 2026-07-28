import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { flagsApi } from "@/features/pentrix/flags/api/flags-api";

export function useSetFlag(challengeId: string) {
  return useMutation({
    mutationFn: (flagValue: string) => flagsApi.setFlag(challengeId, flagValue),
  });
}

export function useSubmitFlag(challengeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ studentId, flagValue }: { studentId: string; flagValue: string }) =>
      flagsApi.submitFlag(challengeId, studentId, flagValue),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["pentrix", "solves", variables.studentId],
      });
      queryClient.invalidateQueries({ queryKey: ["pentrix", "leaderboard"] });
    },
  });
}

export function useSolvesForStudent(studentId: string) {
  return useQuery({
    queryKey: ["pentrix", "solves", studentId],
    queryFn: () => flagsApi.listSolvesForStudent(studentId),
    enabled: !!studentId,
  });
}
