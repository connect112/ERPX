import { apiClient } from "@/api/client";

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
  gender: string | null;
  date_of_birth: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  employment_type: "full_time" | "part_time" | "contract" | "intern";
  employment_status: "active" | "on_leave" | "resigned" | "terminated" | "retired";
  date_of_joining: string;
  date_of_exit: string | null;
  notes: string | null;
  created_at: string;
}

export const employeeApi = {
  me: () => apiClient.get<EmployeePublic>("/employees/me").then((r) => r.data),
};
