import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type VivaCreatePayload, vivaApi } from "@/features/examinations/viva/api/viva-api";

const vivaKey = (courseId: string) => ["examinations", "viva", courseId] as const;
const resultsKey = (courseId: string, vivaId: string) => [...vivaKey(courseId), vivaId, "results"] as const;

export function useVivas(courseId: string) {
  return useQuery({
    queryKey: vivaKey(courseId),
    queryFn: () => vivaApi.list(courseId),
    enabled: !!courseId,
  });
}

export function useCreateViva(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: VivaCreatePayload) => vivaApi.create(courseId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: vivaKey(courseId) }),
  });
}

export function useDeleteViva(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (vivaId: string) => vivaApi.remove(courseId, vivaId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: vivaKey(courseId) }),
  });
}

export function useVivaResults(courseId: string, vivaId: string) {
  return useQuery({
    queryKey: resultsKey(courseId, vivaId),
    queryFn: () => vivaApi.listResults(courseId, vivaId),
    enabled: !!courseId && !!vivaId,
  });
}

export function useRecordVivaResult(courseId: string, vivaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { student_id: string; score: number; remarks?: string }) =>
      vivaApi.recordResult(courseId, vivaId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: resultsKey(courseId, vivaId) }),
  });
}
