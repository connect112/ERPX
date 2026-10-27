import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

export interface Instructor {
  id: string;
  trainer_id: string;
  name: string;
  email: string | null;
  access_from: string | null;
  access_until: string | null;
  status: "upcoming" | "active" | "expired";
  note: string | null;
  created_at: string;
}

export interface InstructorOption {
  trainer_id: string;
  name: string;
  email: string | null;
}

export interface MyAccess {
  role: "admin" | "instructor";
  can_delete: boolean;
  access_from: string | null;
  access_until: string | null;
  status: string | null;
}

export const instructorKeys = {
  list: (id: string) => ["our-internships", "instructors", id] as const,
  options: (id: string) => ["our-internships", "instructors", id, "options"] as const,
  access: (id: string) => ["our-internships", "access", id] as const,
};

const base = (id: string) => `/our-internships/${id}/instructors`;

export const instructorsApi = {
  list: (id: string) => apiClient.get<Instructor[]>(base(id)).then((r) => r.data),
  options: (id: string) => apiClient.get<InstructorOption[]>(`${base(id)}/options`).then((r) => r.data),
  add: (id: string, payload: { trainer_id: string; access_from: string | null; access_until: string | null; note: string | null }) =>
    apiClient.post<Instructor>(base(id), payload).then((r) => r.data),
  update: (id: string, instructorId: string, payload: { access_from?: string | null; access_until?: string | null; note?: string | null }) =>
    apiClient.patch<Instructor>(`${base(id)}/${instructorId}`, payload).then((r) => r.data),
  remove: (id: string, instructorId: string) => apiClient.delete(`${base(id)}/${instructorId}`).then((r) => r.data),
  myAccess: (id: string) => apiClient.get<MyAccess>(`/our-internships/${id}/my-access`).then((r) => r.data),
};

export function useMyAccess(internshipId: string) {
  return useQuery({ queryKey: instructorKeys.access(internshipId), queryFn: () => instructorsApi.myAccess(internshipId), enabled: !!internshipId });
}
