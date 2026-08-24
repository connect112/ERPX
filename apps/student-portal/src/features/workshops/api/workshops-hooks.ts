import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { workshopsApi } from "@/features/workshops/api/workshops-api";

export function useBrowseWorkshops() {
  return useQuery({
    queryKey: ["workshops", "browse"],
    queryFn: () => workshopsApi.browse(),
  });
}

export function useMyWorkshopRegistrations() {
  return useQuery({
    queryKey: ["workshops", "registrations", "me"],
    queryFn: () => workshopsApi.myRegistrations(),
  });
}

export function useRegisterForWorkshop() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (workshopId: string) => workshopsApi.register(workshopId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workshops", "registrations", "me"] });
    },
  });
}
