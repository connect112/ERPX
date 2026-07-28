import { apiClient } from "@/api/client";

export interface StudentPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  student_code: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  course_name: string;
  batch_name: string | null;
  enrollment_date: string;
  status: "active" | "on_hold" | "completed" | "dropped" | "transferred";
  created_at: string;
}

export const studentApi = {
  me: () => apiClient.get<StudentPublic>("/students/me").then((r) => r.data),
};
