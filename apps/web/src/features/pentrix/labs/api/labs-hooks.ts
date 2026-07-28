import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type LabCreatePayload,
  type LabUpdatePayload,
  labsApi,
} from "@/features/pentrix/labs/api/labs-api";

const labsKey = ["pentrix", "labs"] as const;
const labDetailKey = (id: string) => [...labsKey, "detail", id] as const;

export function useLabs() {
  return useQuery({ queryKey: labsKey, queryFn: labsApi.list });
}

export function useLab(id: string | undefined) {
  return useQuery({
    queryKey: labDetailKey(id ?? ""),
    queryFn: () => labsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateLab() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LabCreatePayload) => labsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: labsKey }),
  });
}

export function useUpdateLab(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LabUpdatePayload) => labsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: labsKey }),
  });
}

export function useDeleteLab() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => labsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: labsKey }),
  });
}
