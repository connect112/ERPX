import { apiClient } from "@/api/client";

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

export type LeaveApplicationStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface LeaveApplicationPublic {
  id: string;
  organization_id: string;
  employee_id: string;
  leave_type_id: string;
  approved_by_user_id: string | null;
  start_date: string;
  end_date: string;
  number_of_days: number;
  reason: string;
  status: LeaveApplicationStatus;
  rejection_reason: string | null;
  approved_at: string | null;
  created_at: string;
}

export interface LeaveApplicationListResponse {
  items: LeaveApplicationPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface LeaveBalanceResponse {
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
  // All /me — ownership-gated via get_current_employee (see
  // modules/leave/routes.py): no leave.* permission needed for an
  // employee's own applications, only for viewing/approving others'.
  myLeaveTypes: () => apiClient.get<LeaveTypePublic[]>("/leave/types/me").then((r) => r.data),

  apply: (payload: { leave_type_id: string; start_date: string; end_date: string; reason: string }) =>
    apiClient.post<LeaveApplicationPublic>("/leave/applications/me", payload).then((r) => r.data),

  myApplications: () =>
    apiClient
      .get<LeaveApplicationListResponse>("/leave/applications/me", { params: { limit: 50 } })
      .then((r) => r.data),

  cancel: (id: string) =>
    apiClient.post<LeaveApplicationPublic>(`/leave/applications/${id}/cancel/me`).then((r) => r.data),

  myBalances: (year: number) =>
    apiClient.get<LeaveBalanceResponse[]>("/leave/balances/me", { params: { year } }).then((r) => r.data),
};
