import { apiClient } from "@/api/client";
import type { LeaveApplicationStatus } from "@/features/leave/schemas/leave-schemas";

export interface LeaveTypePublic {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  annual_quota: number;
  is_paid: boolean;
  carry_forward_allowed: boolean;
  max_carry_forward_days: number | null;
  is_active: boolean;
  created_at: string;
}

export interface LeaveTypeCreatePayload {
  name: string;
  code: string;
  annual_quota: number;
  is_paid?: boolean;
  carry_forward_allowed?: boolean;
  max_carry_forward_days?: number;
}

export type LeaveTypeUpdatePayload = Partial<Omit<LeaveTypeCreatePayload, "code">> & {
  is_active?: boolean;
};

export interface LeaveApplicationPublic {
  id: string;
  organization_id: string;
  employee_id: string;
  leave_type_id: string;
  start_date: string;
  end_date: string;
  number_of_days: number;
  reason: string;
  status: LeaveApplicationStatus;
  approved_by_user_id: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  created_at: string;
}

export interface LeaveApplicationListResponse {
  items: LeaveApplicationPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface LeaveApplicationListParams {
  status?: LeaveApplicationStatus;
  skip?: number;
  limit?: number;
}

export interface LeaveApplicationCreatePayload {
  employee_id: string;
  leave_type_id: string;
  start_date: string;
  end_date: string;
  reason: string;
}

export interface LeaveBalance {
  employee_id: string;
  leave_type_id: string;
  leave_type_name: string;
  year: number;
  annual_quota: number;
  days_used: number;
  days_pending: number;
  balance: number;
}

export const leaveApi = {
  listTypes: (isActive?: boolean) =>
    apiClient
      .get<LeaveTypePublic[]>("/leave/types", { params: { is_active: isActive } })
      .then((r) => r.data),

  createType: (payload: LeaveTypeCreatePayload) =>
    apiClient.post<LeaveTypePublic>("/leave/types", payload).then((r) => r.data),

  updateType: (id: string, payload: LeaveTypeUpdatePayload) =>
    apiClient.patch<LeaveTypePublic>(`/leave/types/${id}`, payload).then((r) => r.data),

  listApplications: (params: LeaveApplicationListParams) =>
    apiClient.get<LeaveApplicationListResponse>("/leave/applications", { params }).then((r) => r.data),

  listApplicationsByEmployee: (employeeId: string, params: LeaveApplicationListParams) =>
    apiClient
      .get<LeaveApplicationListResponse>(`/leave/applications/employees/${employeeId}`, { params })
      .then((r) => r.data),

  getApplication: (id: string) =>
    apiClient.get<LeaveApplicationPublic>(`/leave/applications/${id}`).then((r) => r.data),

  apply: (payload: LeaveApplicationCreatePayload) =>
    apiClient.post<LeaveApplicationPublic>("/leave/applications", payload).then((r) => r.data),

  approve: (id: string) =>
    apiClient.post<LeaveApplicationPublic>(`/leave/applications/${id}/approve`).then((r) => r.data),

  reject: (id: string, rejectionReason: string) =>
    apiClient
      .post<LeaveApplicationPublic>(`/leave/applications/${id}/reject`, {
        rejection_reason: rejectionReason,
      })
      .then((r) => r.data),

  cancel: (id: string) =>
    apiClient.post<LeaveApplicationPublic>(`/leave/applications/${id}/cancel`).then((r) => r.data),

  balances: (employeeId: string, year: number) =>
    apiClient
      .get<LeaveBalance[]>(`/leave/balances/employees/${employeeId}`, { params: { year } })
      .then((r) => r.data),
};
