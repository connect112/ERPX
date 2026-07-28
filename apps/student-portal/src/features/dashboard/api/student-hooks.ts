import { useQuery } from "@tanstack/react-query";

import { studentApi } from "@/features/dashboard/api/student-api";

export function useMyStudentProfile() {
  return useQuery({
    queryKey: ["students", "me"],
    queryFn: () => studentApi.me(),
  });
}
