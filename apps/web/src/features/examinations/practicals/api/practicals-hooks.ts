import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type PracticalCreatePayload,
  practicalsApi,
} from "@/features/examinations/practicals/api/practicals-api";

const practicalsKey = (courseId: string) => ["examinations", "practicals", courseId] as const;
const resultsKey = (courseId: string, practicalId: string) =>
  [...practicalsKey(courseId), practicalId, "results"] as const;

export function usePracticals(courseId: string) {
  return useQuery({
    queryKey: practicalsKey(courseId),
    queryFn: () => practicalsApi.list(courseId),
    enabled: !!courseId,
  });
}

export function useCreatePractical(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PracticalCreatePayload) => practicalsApi.create(courseId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: practicalsKey(courseId) }),
  });
}

export function useDeletePractical(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (practicalId: string) => practicalsApi.remove(courseId, practicalId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: practicalsKey(courseId) }),
  });
}

export function usePracticalResults(courseId: string, practicalId: string) {
  return useQuery({
    queryKey: resultsKey(courseId, practicalId),
    queryFn: () => practicalsApi.listResults(courseId, practicalId),
    enabled: !!courseId && !!practicalId,
  });
}

export function useRecordPracticalResult(courseId: string, practicalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { student_id: string; score: number; remarks?: string }) =>
      practicalsApi.recordResult(courseId, practicalId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: resultsKey(courseId, practicalId) }),
  });
}
