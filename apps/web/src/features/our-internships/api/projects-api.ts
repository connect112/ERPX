import { apiClient } from "@/api/client";
import type { StoredFile } from "@/features/our-internships/api/learning-api";

export type ProjectStatus = "draft" | "published" | "closed";
export type SubmissionMethod = "file" | "email" | "repository";

export interface ReferenceLink {
  id: string;
  title: string;
  url: string;
}

export interface Project {
  id: string;
  internship_id: string;
  title: string;
  description: string | null;
  objectives: string | null;
  rules: string | null;
  submission_instructions: string | null;
  reference_links: ReferenceLink[];
  allow_file: boolean;
  allow_email: boolean;
  allow_repository: boolean;
  submission_email: string | null;
  max_files: number;
  capacity: number | null;
  starts_at: string | null;
  deadline_at: string | null;
  allow_late: boolean;
  status: ProjectStatus;
  created_at: string;
  documents: StoredFile[];
  templates: StoredFile[];
  chosen_count: number;
  submitted_count: number;
}

export interface ProjectPayload {
  title: string;
  description: string | null;
  objectives: string | null;
  rules: string | null;
  submission_instructions: string | null;
  reference_links: ReferenceLink[];
  allow_file: boolean;
  allow_email: boolean;
  allow_repository: boolean;
  submission_email: string | null;
  max_files: number;
  capacity: number | null;
  starts_at: string | null;
  deadline_at: string | null;
  allow_late: boolean;
  status?: ProjectStatus;
}

export interface ProjectSelectionRow {
  selection_id: string;
  student_name: string;
  student_email: string;
  project_id: string | null;
  project_title: string | null;
  chosen_at: string | null;
  submitted: boolean;
  method: SubmissionMethod | null;
  submitted_at: string | null;
  is_late: boolean;
  resubmission_count: number;
  repository_url: string | null;
  note: string | null;
  files: StoredFile[];
  received_at: string | null;
}

export const projectKeys = {
  list: (id: string) => ["our-internships", "projects", id] as const,
  selections: (id: string) => ["our-internships", "projects", id, "selections"] as const,
};

const base = (id: string) => `/our-internships/${id}`;
const multipart = { headers: { "Content-Type": "multipart/form-data" } };

export const projectsApi = {
  list: (id: string) => apiClient.get<Project[]>(`${base(id)}/projects`).then((r) => r.data),
  create: (id: string, payload: ProjectPayload) => apiClient.post<Project>(`${base(id)}/projects`, payload).then((r) => r.data),
  update: (id: string, projectId: string, payload: Partial<ProjectPayload>) =>
    apiClient.patch<Project>(`${base(id)}/projects/${projectId}`, payload).then((r) => r.data),
  remove: (id: string, projectId: string) => apiClient.delete(`${base(id)}/projects/${projectId}`).then((r) => r.data),
  addFile: (id: string, projectId: string, kind: "document" | "template", file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<StoredFile>(`${base(id)}/projects/${projectId}/files`, form, { ...multipart, params: { kind } })
      .then((r) => r.data);
  },
  removeFile: (id: string, projectId: string, fileId: string) =>
    apiClient.delete(`${base(id)}/projects/${projectId}/files/${fileId}`).then((r) => r.data),
  selections: (id: string) => apiClient.get<ProjectSelectionRow[]>(`${base(id)}/project-selections`).then((r) => r.data),
  markReceived: (id: string, projectId: string, selectionId: string, received: boolean) =>
    apiClient
      .put<ProjectSelectionRow>(`${base(id)}/projects/${projectId}/submissions/${selectionId}/received`, { received })
      .then((r) => r.data),
};
