import { apiClient } from "@/api/client";

export interface AttendanceRecordPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  employee_id: string;
  attendance_date: string;
  check_in_time: string | null;
  check_out_time: string | null;
  work_hours: number | null;
  status: "present" | "absent" | "half_day" | "on_leave" | "holiday" | "week_off";
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

export const myAttendanceApi = {
  // /employee/... — ownership-gated via get_current_employee: every
  // employee has an Employee record, not every employee has a Trainer
  // one, so this is the path that works for any designation (see
  // modules/attendance/routes.py).
  checkIn: () =>
    apiClient.post<AttendanceRecordPublic>("/attendance/employee/check-in/me", {}).then((r) => r.data),

  checkOut: () =>
    apiClient.post<AttendanceRecordPublic>("/attendance/employee/check-out/me", {}).then((r) => r.data),

  myAttendance: () =>
    apiClient
      .get<AttendanceListResponse>("/attendance/employee/me", { params: { limit: 30 } })
      .then((r) => r.data),
};
