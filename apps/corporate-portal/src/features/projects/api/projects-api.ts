import { apiClient } from "@/api/client";

export interface ProjectPublic {
  id: string;
  organization_id: string;
  client_id: string;
  project_manager_employee_id: string | null;
  project_code: string;
  name: string;
  description: string | null;
  project_type: "vapt" | "soc" | "consulting" | "training" | "other";
  status: "planned" | "in_progress" | "on_hold" | "completed" | "cancelled";
  start_date: string;
  end_date: string | null;
  budget_amount: number | null;
  notes: string | null;
  created_at: string;
}

export const projectsApi = {
  myProjects: () => apiClient.get<ProjectPublic[]>("/corporate/projects/me").then((r) => r.data),
};
