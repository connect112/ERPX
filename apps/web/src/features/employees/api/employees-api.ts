import { apiClient } from "@/api/client";
import type {
  EmploymentStatus,
  EmploymentType,
  Gender,
} from "@/features/employees/schemas/employee-schemas";

export interface EmployeePublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  user_id: string | null;
  department_id: string | null;
  designation_id: string | null;
  reporting_manager_id: string | null;
  employee_code: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  gender: Gender | null;
  date_of_birth: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  employment_type: EmploymentType;
  employment_status: EmploymentStatus;
  date_of_joining: string;
  date_of_exit: string | null;
  notes: string | null;
  created_at: string;
}

export interface EmployeeListResponse {
  items: EmployeePublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface EmployeeListParams {
  department_id?: string;
  designation_id?: string;
  employment_status?: EmploymentStatus;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface EmployeeCreatePayload {
  employee_code: string;
  full_name: string;
  branch_id?: string;
  department_id?: string;
  designation_id?: string;
  reporting_manager_id?: string;
  email?: string;
  phone?: string;
  gender?: Gender;
  date_of_birth?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  employment_type?: EmploymentType;
  date_of_joining: string;
  notes?: string;
}

export type EmployeeUpdatePayload = Partial<Omit<EmployeeCreatePayload, "employee_code" | "date_of_joining">>;

export const employeesApi = {
  list: (params: EmployeeListParams) =>
    apiClient.get<EmployeeListResponse>("/employees", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<EmployeePublic>(`/employees/${id}`).then((r) => r.data),

  create: (payload: EmployeeCreatePayload) =>
    apiClient.post<EmployeePublic>("/employees", payload).then((r) => r.data),

  update: (id: string, payload: EmployeeUpdatePayload) =>
    apiClient.patch<EmployeePublic>(`/employees/${id}`, payload).then((r) => r.data),

  changeStatus: (id: string, employmentStatus: EmploymentStatus, dateOfExit?: string) =>
    apiClient
      .post<EmployeePublic>(`/employees/${id}/status`, {
        employment_status: employmentStatus,
        date_of_exit: dateOfExit,
      })
      .then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/employees/${id}`).then((r) => r.data),
};
