import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";
import type { ImportResult, ImportSource, SyncResult } from "@/features/institutions/api/institutions-api";

export interface Destination {
  institution_id: string;
  institution_name: string;
  events: { id: string; name: string }[];
}

export interface StudentAddResult {
  student_id: string;
  created: boolean;
  message: string;
}

export interface StudentUpdate {
  event_id: string;
  name?: string;
  email?: string;
  phone?: string | null;
  individual_score?: number | null;
  remarks?: string | null;
}

export const studentKeys = {
  destinations: (id: string) => ["our-internships", "students", id, "destinations"] as const,
};

const base = (id: string) => `/our-internships/${id}/students`;
// apiClient defaults to a JSON Content-Type, under which axios turns a FormData body into JSON; naming multipart lets the browser add the boundary.
const multipart = { headers: { "Content-Type": "multipart/form-data" } };

export const studentsApi = {
  destinations: (id: string) => apiClient.get<Destination[]>(`${base(id)}/destinations`).then((r) => r.data),
  add: (id: string, payload: { event_id: string; name: string; email: string; phone: string | null }) =>
    apiClient.post<StudentAddResult>(base(id), payload).then((r) => r.data),
  importList: (id: string, eventId: string, source: ImportSource, dryRun: boolean) => {
    const form = new FormData();
    form.append("event_id", eventId);
    if ("file" in source) form.append("file", source.file);
    else form.append("text", source.text);
    form.append("dry_run", dryRun ? "true" : "false");
    return apiClient.post<ImportResult>(`${base(id)}/import`, form, multipart).then((r) => r.data);
  },
  update: (id: string, studentId: string, payload: StudentUpdate) =>
    apiClient.patch<{ message: string }>(`${base(id)}/${studentId}`, payload).then((r) => r.data),
  remove: (id: string, studentId: string, eventId: string) =>
    apiClient.delete<{ message: string }>(`${base(id)}/${studentId}`, { params: { event_id: eventId } }).then((r) => r.data),
  /** Fetch the people of the linked exams and hackathons into the student list. */
  sync: (id: string) => apiClient.post<SyncResult>(`${base(id)}/sync`).then((r) => r.data),
};

export function useDestinations(internshipId: string) {
  return useQuery({ queryKey: studentKeys.destinations(internshipId), queryFn: () => studentsApi.destinations(internshipId) });
}
