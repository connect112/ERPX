import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

export interface MyInternship {
  id: string;
  selection_id: string;
  title: string;
  description: string | null;
  status: string;
  open_assignments: number;
  open_exams: number;
}

export interface StoredFile {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  url: string | null;
}

export interface MyExam {
  id: string;
  title: string;
  description: string | null;
  duration_minutes: number;
  status: "open" | "closed";
  state: "not_started" | "in_progress" | "submitted";
  url: string;
  score: number | null;
  total_marks: number | null;
  submitted_at: string | null;
}

export interface MySubmission {
  submitted_at: string;
  is_late: boolean;
  note: string | null;
  files: StoredFile[];
  reviewed: boolean;
  score: number | null;
  rubric_scores: Record<string, number> | null;
  feedback: string | null;
  can_resubmit: boolean;
}

export interface MyAssignment {
  id: string;
  title: string;
  description: string | null;
  tasks: { id: string; title: string; details: string | null }[];
  instructions: string | null;
  max_marks: number;
  rubric: { id: string; criterion: string; points: number }[];
  starts_at: string | null;
  deadline_at: string | null;
  allow_late: boolean;
  max_files: number;
  status: "published" | "closed";
  files: StoredFile[];
  can_submit: boolean;
  submission: MySubmission | null;
}

const base = "/my-internships";

export const myInternshipApi = {
  list: () => apiClient.get<MyInternship[]>(base).then((r) => r.data),
  get: (id: string) => apiClient.get<MyInternship>(`${base}/${id}`).then((r) => r.data),
  exams: (id: string) => apiClient.get<MyExam[]>(`${base}/${id}/exams`).then((r) => r.data),
  assignments: (id: string) => apiClient.get<MyAssignment[]>(`${base}/${id}/assignments`).then((r) => r.data),
  submit: (id: string, assignmentId: string, payload: { note: string; files: File[] }) => {
    const form = new FormData();
    if (payload.note.trim()) form.append("note", payload.note.trim());
    payload.files.forEach((f) => form.append("files", f));
    // apiClient defaults to a JSON Content-Type; naming multipart lets the browser add the boundary.
    return apiClient
      .post<MyAssignment>(`${base}/${id}/assignments/${assignmentId}/submission`, form, { headers: { "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },
};

export const myInternshipKeys = {
  all: ["my-internships"] as const,
  list: ["my-internships", "list"] as const,
  detail: (id: string) => ["my-internships", "detail", id] as const,
  exams: (id: string) => ["my-internships", "exams", id] as const,
  assignments: (id: string) => ["my-internships", "assignments", id] as const,
};

export function useMyInternshipList() {
  return useQuery({ queryKey: myInternshipKeys.list, queryFn: myInternshipApi.list });
}

export function useMyInternshipDetail(id: string) {
  return useQuery({ queryKey: myInternshipKeys.detail(id), queryFn: () => myInternshipApi.get(id), enabled: !!id });
}

export function useMyExams(id: string) {
  return useQuery({ queryKey: myInternshipKeys.exams(id), queryFn: () => myInternshipApi.exams(id), enabled: !!id });
}

export function useMyAssignments(id: string) {
  return useQuery({ queryKey: myInternshipKeys.assignments(id), queryFn: () => myInternshipApi.assignments(id), enabled: !!id });
}

export function useSubmitAssignment(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (v: { assignmentId: string; note: string; files: File[] }) => myInternshipApi.submit(id, v.assignmentId, { note: v.note, files: v.files }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: myInternshipKeys.all }),
  });
}
