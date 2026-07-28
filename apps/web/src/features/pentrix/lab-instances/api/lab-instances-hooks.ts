import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { labInstancesApi } from "@/features/pentrix/lab-instances/api/lab-instances-api";

const instancesKey = (studentId: string) => ["pentrix", "lab-instances", studentId] as const;

export function useLabInstancesForStudent(studentId: string) {
  return useQuery({
    queryKey: instancesKey(studentId),
    queryFn: () => labInstancesApi.listForStudent(studentId),
    enabled: !!studentId,
  });
}

export function useLaunchLab(studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (labId: string) => labInstancesApi.launch(labId, studentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: instancesKey(studentId) }),
  });
}

export function useStopLabInstance(studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (instanceId: string) => labInstancesApi.stop(instanceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: instancesKey(studentId) }),
  });
}
