import { useQuery } from "@tanstack/react-query";

import { contractsApi } from "@/features/contracts/api/contracts-api";

export function useMyContracts() {
  return useQuery({
    queryKey: ["contracts", "me"],
    queryFn: () => contractsApi.myContracts(),
  });
}
