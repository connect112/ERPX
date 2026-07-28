import { apiClient } from "@/api/client";
import type { ProjectStatus, ProjectType } from "@/features/corporate/projects/schemas/project-schemas";

export interface ProjectPublic {
  id: string;
  organization_id: string;
  client_id: string;
  project_manager_employee_id: string | null;
  project_code: string;
  name: string;
  description: string | null;
  project_type: ProjectType;
  status: ProjectStatus;
  start_date: string;
  end_date: string | null;
  budget_amount: number | null;
  notes: string | null;
  created_at: string;
}

export interface ProjectListResponse {
  items: ProjectPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface ProjectListParams {
  client_id?: string;
  project_type?: ProjectType;
  status?: ProjectStatus;
  skip?: number;
  limit?: number;
}

export interface ProjectCreatePayload {
  client_id: string;
  project_code: string;
  name: string;
  description?: string;
  project_type?: ProjectType;
  project_manager_employee_id?: string;
  start_date: string;
  end_date?: string;
  budget_amount?: number;
  notes?: string;
}

export interface ProjectUpdatePayload {
  name?: string;
  description?: string;
  project_manager_employee_id?: string;
  start_date?: string;
  end_date?: string;
  budget_amount?: number;
  notes?: string;
}

export const projectsApi = {
  list: (params: ProjectListParams) =>
    apiClient.get<ProjectListResponse>("/corporate/projects", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<ProjectPublic>(`/corporate/projects/${id}`).then((r) => r.data),

  create: (payload: ProjectCreatePayload) =>
    apiClient.post<ProjectPublic>("/corporate/projects", payload).then((r) => r.data),

  update: (id: string, payload: ProjectUpdatePayload) =>
    apiClient.patch<ProjectPublic>(`/corporate/projects/${id}`, payload).then((r) => r.data),

  changeStatus: (id: string, status: ProjectStatus) =>
    apiClient.post<ProjectPublic>(`/corporate/projects/${id}/status`, { status }).then((r) => r.data),
};
