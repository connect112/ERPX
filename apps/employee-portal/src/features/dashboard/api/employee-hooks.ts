import { useQuery } from "@tanstack/react-query";

import { employeeApi } from "@/features/dashboard/api/employee-api";

export function useMyEmployeeProfile() {
  return useQuery({
    queryKey: ["employees", "me"],
    queryFn: () => employeeApi.me(),
  });
}
