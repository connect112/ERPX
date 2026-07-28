import { apiClient } from "@/api/client";
import type { ApprovalRequestStatus } from "@/features/workflow/schemas/workflow-schemas";

export interface WorkflowStepPublic {
  id: string;
  workflow_id: string;
  step_order: number;
  approver_role_id: string;
  name: string | null;
}

export interface WorkflowPublic {
  id: string;
  organization_id: string;
  entity_type: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface WorkflowDetailPublic extends WorkflowPublic {
  steps: WorkflowStepPublic[];
}

export interface WorkflowListResponse {
  items: WorkflowPublic[];
  total: number;
}

export interface WorkflowStepInputPayload {
  step_order: number;
  approver_role_id: string;
  name?: string;
}

export interface WorkflowCreatePayload {
  entity_type: string;
  name: string;
  description?: string;
  steps: WorkflowStepInputPayload[];
}

export interface WorkflowUpdatePayload {
  name?: string;
  description?: string;
  is_active?: boolean;
}

export interface ApprovalRequestPublic {
  id: string;
  organization_id: string;
  workflow_id: string;
  entity_type: string;
  entity_id: string;
  requested_by_user_id: string;
  current_step_order: number;
  status: ApprovalRequestStatus;
  resolved_at: string | null;
  created_at: string;
}

export interface ApprovalRequestListResponse {
  items: ApprovalRequestPublic[];
  total: number;
}

export interface ApprovalActionPublic {
  id: string;
  request_id: string;
  step_order: number;
  actor_user_id: string;
  decision: "approved" | "rejected";
  comment: string | null;
  acted_at: string;
}

export const workflowApi = {
  listWorkflows: (params: { entity_type?: string; skip?: number; limit?: number }) =>
    apiClient.get<WorkflowListResponse>("/workflow/workflows", { params }).then((r) => r.data),

  getWorkflow: (id: string) =>
    apiClient.get<WorkflowDetailPublic>(`/workflow/workflows/${id}`).then((r) => r.data),

  createWorkflow: (payload: WorkflowCreatePayload) =>
    apiClient.post<WorkflowDetailPublic>("/workflow/workflows", payload).then((r) => r.data),

  updateWorkflow: (id: string, payload: WorkflowUpdatePayload) =>
    apiClient.patch<WorkflowPublic>(`/workflow/workflows/${id}`, payload).then((r) => r.data),

  deleteWorkflow: (id: string) => apiClient.delete(`/workflow/workflows/${id}`).then((r) => r.data),

  listAllRequests: (params: { status?: ApprovalRequestStatus; skip?: number; limit?: number }) =>
    apiClient.get<ApprovalRequestListResponse>("/workflow/requests", { params }).then((r) => r.data),

  getRequest: (id: string) =>
    apiClient.get<ApprovalRequestPublic>(`/workflow/requests/${id}`).then((r) => r.data),

  listRequestActions: (id: string) =>
    apiClient.get<ApprovalActionPublic[]>(`/workflow/requests/${id}/actions`).then((r) => r.data),

  listMyPendingApprovals: () =>
    apiClient.get<ApprovalRequestPublic[]>("/workflow/requests/me/pending-approvals").then((r) => r.data),

  approveRequest: (id: string, comment?: string) =>
    apiClient.post<ApprovalRequestPublic>(`/workflow/requests/${id}/approve`, { comment }).then((r) => r.data),

  rejectRequest: (id: string, comment?: string) =>
    apiClient.post<ApprovalRequestPublic>(`/workflow/requests/${id}/reject`, { comment }).then((r) => r.data),
};
