import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type TrainerCreatePayload,
  type TrainerUpdatePayload,
  trainersApi,
} from "@/features/trainers/api/trainers-api";

const trainersKeys = {
  all: ["trainers"] as const,
  list: (params: { skip?: number; limit?: number }) => [...trainersKeys.all, "list", params] as const,
};

export function useTrainersList(params: { skip?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: trainersKeys.list(params),
    queryFn: () => trainersApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useCreateTrainer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TrainerCreatePayload) => trainersApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: trainersKeys.all }),
  });
}

export function useUpdateTrainer(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TrainerUpdatePayload) => trainersApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: trainersKeys.all }),
  });
}

export function useDeleteTrainer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => trainersApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: trainersKeys.all }),
  });
}
