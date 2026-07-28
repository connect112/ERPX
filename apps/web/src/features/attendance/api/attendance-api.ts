import { apiClient } from "@/api/client";
import type { AttendanceStatus } from "@/features/attendance/schemas/attendance-schemas";

export interface AttendanceRecordPublic {
  id: string;
  organization_id: string;
  employee_id: string;
  branch_id: string | null;
  attendance_date: string;
  status: AttendanceStatus;
  check_in_time: string | null;
  check_out_time: string | null;
  work_hours: number | null;
  is_regularized: boolean;
  regularization_reason: string | null;
  remarks: string | null;
  created_at: string;
}

export interface AttendanceListResponse {
  items: AttendanceRecordPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface AttendanceListParams {
  branch_id?: string;
  attendance_date?: string;
  status?: AttendanceStatus;
  skip?: number;
  limit?: number;
}

export interface EmployeeAttendanceListParams {
  date_from?: string;
  date_to?: string;
  skip?: number;
  limit?: number;
}

export interface MonthlyAttendanceSummary {
  employee_id: string;
  year: number;
  month: number;
  present_days: number;
  absent_days: number;
  half_days: number;
  leave_days: number;
  holiday_days: number;
  week_off_days: number;
  total_work_hours: number;
}

export interface MarkAttendancePayload {
  employee_id: string;
  attendance_date: string;
  status: AttendanceStatus;
  remarks?: string;
}

export interface CheckInPayload {
  employee_id: string;
  check_in_time?: string;
}

export interface CheckOutPayload {
  employee_id: string;
  check_out_time?: string;
}

export interface RegularizeAttendancePayload {
  check_in_time?: string;
  check_out_time?: string;
  status?: AttendanceStatus;
  regularization_reason: string;
}

export const attendanceApi = {
  list: (params: AttendanceListParams) =>
    apiClient.get<AttendanceListResponse>("/attendance", { params }).then((r) => r.data),

  listByEmployee: (employeeId: string, params: EmployeeAttendanceListParams) =>
    apiClient
      .get<AttendanceListResponse>(`/attendance/employees/${employeeId}`, { params })
      .then((r) => r.data),

  summary: (employeeId: string, year: number, month: number) =>
    apiClient
      .get<MonthlyAttendanceSummary>(`/attendance/employees/${employeeId}/summary`, {
        params: { year, month },
      })
      .then((r) => r.data),

  mark: (payload: MarkAttendancePayload) =>
    apiClient.post<AttendanceRecordPublic>("/attendance/mark", payload).then((r) => r.data),

  checkIn: (payload: CheckInPayload) =>
    apiClient.post<AttendanceRecordPublic>("/attendance/check-in", payload).then((r) => r.data),

  checkOut: (payload: CheckOutPayload) =>
    apiClient.post<AttendanceRecordPublic>("/attendance/check-out", payload).then((r) => r.data),

  regularize: (id: string, payload: RegularizeAttendancePayload) =>
    apiClient
      .post<AttendanceRecordPublic>(`/attendance/${id}/regularize`, payload)
      .then((r) => r.data),
};
