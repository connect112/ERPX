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
}

export interface DesignationUpdatePayload {
  title?: string;
  grade_level?: number;
  description?: string;
  is_active?: boolean;
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
};
