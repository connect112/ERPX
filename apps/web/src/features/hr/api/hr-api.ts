import { apiClient } from "@/api/client";

export interface DepartmentPublic {
  id: string;
  organization_id: string;
  parent_department_id: string | null;
  head_employee_id: string | null;
  name: string;
  code: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface DesignationPublic {
  id: string;
  organization_id: string;
  title: string;
  code: string;
  grade_level: number | null;
  description: string | null;
  is_active: boolean;
  // What EmployeeService.invite_employee grants an employee holding this
  // designation, beyond the basic employee-portal login every employee
  // gets regardless — see migration 0041.
  linked_role_id: string | null;
  grants_trainer_access: boolean;
  created_at: string;
}

export interface DepartmentCreatePayload {
  name: string;
  code: string;
  parent_department_id?: string;
  head_employee_id?: string;
  description?: string;
}

export interface DepartmentUpdatePayload {
  name?: string;
  parent_department_id?: string;
  head_employee_id?: string;
  description?: string;
  is_active?: boolean;
}

export interface DesignationCreatePayload {
  title: string;
  code: string;
  grade_level?: number;
  description?: string;
  linked_role_id?: string;
  grants_trainer_access?: boolean;
}

export interface DesignationUpdatePayload {
  title?: string;
  grade_level?: number;
  description?: string;
  is_active?: boolean;
  linked_role_id?: string | null;
  grants_trainer_access?: boolean;
}

export interface HrSettingsPublic {
  organization_id: string;
  // Python's date.weekday() convention: Monday=0 .. Sunday=6.
  week_off_days: number[];
  // Both null until an admin sets them via the automation card below --
  // see modules/payroll/tasks.py: once both are set, the last-working-day
  // auto-generated run is also auto-finalized and emailed to employees.
  default_salary_payable_account_id: string | null;
  default_expense_reimbursement_component_id: string | null;
}

export interface HrSettingsUpdatePayload {
  week_off_days?: number[];
  default_salary_payable_account_id?: string;
  default_expense_reimbursement_component_id?: string;
}

export const hrApi = {
  listDepartments: (isActive?: boolean) =>
    apiClient
      .get<DepartmentPublic[]>("/hr/departments", { params: { is_active: isActive } })
      .then((r) => r.data),

  createDepartment: (payload: DepartmentCreatePayload) =>
    apiClient.post<DepartmentPublic>("/hr/departments", payload).then((r) => r.data),

  updateDepartment: (id: string, payload: DepartmentUpdatePayload) =>
    apiClient.patch<DepartmentPublic>(`/hr/departments/${id}`, payload).then((r) => r.data),

  listDesignations: (isActive?: boolean) =>
    apiClient
      .get<DesignationPublic[]>("/hr/designations", { params: { is_active: isActive } })
      .then((r) => r.data),

  createDesignation: (payload: DesignationCreatePayload) =>
    apiClient.post<DesignationPublic>("/hr/designations", payload).then((r) => r.data),

  updateDesignation: (id: string, payload: DesignationUpdatePayload) =>
    apiClient.patch<DesignationPublic>(`/hr/designations/${id}`, payload).then((r) => r.data),

  getSettings: () => apiClient.get<HrSettingsPublic>("/hr/settings").then((r) => r.data),

  updateSettings: (payload: HrSettingsUpdatePayload) =>
    apiClient.patch<HrSettingsPublic>("/hr/settings", payload).then((r) => r.data),
};
