import { useQuery } from "@tanstack/react-query";

import { projectsApi } from "@/features/projects/api/projects-api";

export function useMyProjects() {
  return useQuery({
    queryKey: ["projects", "me"],
    queryFn: () => projectsApi.myProjects(),
  });
}
