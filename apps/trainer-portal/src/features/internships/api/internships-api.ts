import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

export interface AssignedInternship {
  id: string;
  title: string;
  description: string | null;
  status: string;
  access_from: string | null;
  access_until: string | null;
}

export const internshipsApi = {
  mine: () => apiClient.get<AssignedInternship[]>("/instructing-internships").then((r) => r.data),
};

/** The internships an admin has given this trainer access to, right now. Ones whose period ended are not returned. */
export function useMyInternships() {
  return useQuery({ queryKey: ["instructing-internships"], queryFn: () => internshipsApi.mine() });
}
