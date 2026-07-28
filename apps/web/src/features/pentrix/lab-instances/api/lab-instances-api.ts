import { apiClient } from "@/api/client";

export type LabInstanceStatus = "provisioning" | "running" | "stopped" | "expired" | "failed";

export interface LabInstancePublic {
  id: string;
  lab_id: string;
  student_id: string;
  environment_ref: string | null;
  access_endpoint: string | null;
  status: LabInstanceStatus;
  started_at: string;
  expires_at: string;
  stopped_at: string | null;
}

export const labInstancesApi = {
  launch: (labId: string, studentId: string) =>
    apiClient
      .post<LabInstancePublic>(`/pentrix/labs/${labId}/launch`, { student_id: studentId })
      .then((r) => r.data),

  listForStudent: (studentId: string) =>
    apiClient
      .get<LabInstancePublic[]>(`/pentrix/students/${studentId}/instances`)
      .then((r) => r.data),

  stop: (instanceId: string) =>
    apiClient.post<LabInstancePublic>(`/pentrix/instances/${instanceId}/stop`).then((r) => r.data),
};
