import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type WorkflowCreatePayload,
  type WorkflowUpdatePayload,
  workflowApi,
} from "@/features/workflow/api/workflow-api";
import type { ApprovalRequestStatus } from "@/features/workflow/schemas/workflow-schemas";

const workflowKeys = {
  all: ["workflow"] as const,
  workflows: (params: { entity_type?: string; skip?: number; limit?: number }) =>
    [...workflowKeys.all, "workflows", params] as const,
  workflow: (id: string) => [...workflowKeys.all, "workflows", id] as const,
  requests: (params: { status?: ApprovalRequestStatus; skip?: number; limit?: number }) =>
    [...workflowKeys.all, "requests", params] as const,
  request: (id: string) => [...workflowKeys.all, "requests", id] as const,
  actions: (id: string) => [...workflowKeys.all, "requests", id, "actions"] as const,
  myApprovals: () => [...workflowKeys.all, "my-approvals"] as const,
};

export function useWorkflowsList(params: { entity_type?: string; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: workflowKeys.workflows(params),
    queryFn: () => workflowApi.listWorkflows(params),
    placeholderData: keepPreviousData,
  });
}

export function useWorkflow(id: string | undefined) {
  return useQuery({
    queryKey: workflowKeys.workflow(id ?? ""),
    queryFn: () => workflowApi.getWorkflow(id as string),
    enabled: !!id,
  });
}

export function useCreateWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: WorkflowCreatePayload) => workflowApi.createWorkflow(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: workflowKeys.all }),
  });
}

export function useUpdateWorkflow(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: WorkflowUpdatePayload) => workflowApi.updateWorkflow(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: workflowKeys.all }),
  });
}

export function useDeleteWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => workflowApi.deleteWorkflow(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: workflowKeys.all }),
  });
}

export function useAllRequests(params: { status?: ApprovalRequestStatus; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: workflowKeys.requests(params),
    queryFn: () => workflowApi.listAllRequests(params),
    placeholderData: keepPreviousData,
  });
}

export function useRequestActions(id: string | undefined) {
  return useQuery({
    queryKey: workflowKeys.actions(id ?? ""),
    queryFn: () => workflowApi.listRequestActions(id as string),
    enabled: !!id,
  });
}

export function useMyPendingApprovals() {
  return useQuery({
    queryKey: workflowKeys.myApprovals(),
    queryFn: () => workflowApi.listMyPendingApprovals(),
  });
}

export function useApproveRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, comment }: { id: string; comment?: string }) =>
      workflowApi.approveRequest(id, comment),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: workflowKeys.all }),
  });
}

export function useRejectRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, comment }: { id: string; comment?: string }) =>
      workflowApi.rejectRequest(id, comment),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: workflowKeys.all }),
  });
}
