import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type TimetableEntryCreatePayload,
  timetableApi,
} from "@/features/timetable/api/timetable-api";

const timetableKeys = {
  all: ["timetable"] as const,
  forBatch: (batchId: string) => [...timetableKeys.all, "batch", batchId] as const,
};

export function useTimetableForBatch(batchId: string) {
  return useQuery({
    queryKey: timetableKeys.forBatch(batchId),
    queryFn: () => timetableApi.listForBatch(batchId),
    enabled: !!batchId,
  });
}

export function useCreateTimetableEntry(batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TimetableEntryCreatePayload) => timetableApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: timetableKeys.forBatch(batchId) }),
  });
}

export function useDeleteTimetableEntry(batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => timetableApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: timetableKeys.forBatch(batchId) }),
  });
}
