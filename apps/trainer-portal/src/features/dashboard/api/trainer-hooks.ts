import { useQuery } from "@tanstack/react-query";

import { trainerApi } from "@/features/dashboard/api/trainer-api";

export function useMyTrainerProfile() {
  return useQuery({
    queryKey: ["trainers", "me"],
    queryFn: () => trainerApi.me(),
  });
}
