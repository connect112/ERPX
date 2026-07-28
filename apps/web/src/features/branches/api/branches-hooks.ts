import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type BranchCreatePayload,
  type BranchUpdatePayload,
  branchesApi,
} from "@/features/branches/api/branches-api";

const branchesKey = (organizationId: string) => ["branches", organizationId] as const;

export function useBranches(organizationId: string | undefined) {
  return useQuery({
    queryKey: branchesKey(organizationId ?? ""),
    queryFn: () => branchesApi.list(organizationId as string),
    enabled: !!organizationId,
  });
}

export function useCreateBranch(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BranchCreatePayload) => branchesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: branchesKey(organizationId) }),
  });
}

export function useUpdateBranch(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: BranchUpdatePayload }) =>
      branchesApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: branchesKey(organizationId) }),
  });
}

export function useDeleteBranch(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => branchesApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: branchesKey(organizationId) }),
  });
}
