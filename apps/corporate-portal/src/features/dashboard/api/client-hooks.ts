import { useQuery } from "@tanstack/react-query";

import { clientApi } from "@/features/dashboard/api/client-api";

export function useMyClientProfile() {
  return useQuery({
    queryKey: ["clients", "me"],
    queryFn: () => clientApi.me(),
  });
}
